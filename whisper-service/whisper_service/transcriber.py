"""faster-whisper model singleton — loaded once, reused per request."""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from faster_whisper import WhisperModel

    from whisper_service.config import Config

logger = logging.getLogger(__name__)

_model: WhisperModel | None = None
_config: Config | None = None
_ready = False
_load_lock = threading.Lock()
_transcribe_lock = threading.Lock()


def init(config: Config) -> None:
    global _config
    _config = config


def load() -> None:
    global _model, _ready
    if _config is None:
        raise RuntimeError("transcriber.init() must be called before load()")

    with _load_lock:
        if _ready:
            return
        from faster_whisper import WhisperModel

        logger.info(
            "Carregando modelo Whisper %s (compute=%s)...",
            _config.model_size,
            _config.compute_type,
        )
        _model = WhisperModel(
            _config.model_size,
            device="cpu",
            compute_type=_config.compute_type,
        )
        _ready = True
        logger.info("Modelo Whisper pronto")


def is_ready_state() -> bool:
    return _ready


def transcribe(audio_path: str, language: str) -> tuple[str, float]:
    if not _ready or _model is None:
        raise RuntimeError("Modelo ainda não carregado")

    with _transcribe_lock:
        segments, info = _model.transcribe(
            audio_path,
            language=language,
            beam_size=5,
        )
        parts: list[str] = []
        duration_s = 0.0
        for segment in segments:
            text = segment.text.strip()
            if text:
                parts.append(text)
            duration_s = max(duration_s, segment.end)

        if duration_s <= 0 and info.duration:
            duration_s = float(info.duration)

        return " ".join(parts), duration_s


def reset_for_tests() -> None:
    """Clear singleton state (tests only)."""
    global _model, _config, _ready
    _model = None
    _config = None
    _ready = False
