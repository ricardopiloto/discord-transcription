"""Hook py-cord voice decrypt path to observe DAVE/Crypto failures.

Hook site (py-cord voice receive):
``discord.voice.receive.reader.PacketDecryptor.decrypt_rtp``

DAVE decrypt failures are often swallowed and replaced with Opus silence; we detect
those via ``_dave_consecutive_failures`` increments when the result is silence-sized.
Outer NaCl ``CryptoError`` is also reported.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

_installed = False
_on_failure: Callable[[], None] | None = None


def install_dave_decrypt_hooks(on_failure: Callable[[], None]) -> None:
    """Patch PacketDecryptor.decrypt_rtp once; ``on_failure`` may run on voice thread."""
    global _installed, _on_failure
    _on_failure = on_failure
    if _installed:
        return

    try:
        from discord.voice.receive.reader import PacketDecryptor
    except ImportError as exc:
        logger.warning("[dave_hooks] PacketDecryptor indisponível: %s", exc)
        return

    try:
        from discord.voice.receive.reader import OPUS_SILENCE
    except ImportError:
        OPUS_SILENCE = b"\xf8\xff\xfe"  # type: ignore[misc,assignment]

    original = PacketDecryptor.decrypt_rtp

    def patched(self: Any, packet: Any) -> bytes:
        prev = dict(getattr(self, "_dave_consecutive_failures", {}))
        try:
            result = original(self, packet)
        except Exception as exc:
            if exc.__class__.__name__ == "CryptoError":
                _notify_failure()
            raise

        curr = getattr(self, "_dave_consecutive_failures", {})
        for ssrc, count in curr.items():
            if count <= prev.get(ssrc, 0):
                continue
            # New DAVE failure recorded for this SSRC.
            if result == OPUS_SILENCE or (isinstance(result, (bytes, bytearray)) and len(result) <= 3):
                _notify_failure()
            break
        return result

    PacketDecryptor.decrypt_rtp = patched  # type: ignore[method-assign]
    _installed = True
    logger.info("[dave_hooks] Patch instalado em PacketDecryptor.decrypt_rtp")


def _notify_failure() -> None:
    cb = _on_failure
    if cb is None:
        return
    try:
        cb()
    except Exception:
        logger.exception("[dave_hooks] on_failure callback falhou")
