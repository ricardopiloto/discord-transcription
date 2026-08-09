"""DAVE decrypt failure counter, cooldown, and recovery orchestration helpers."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from cronista.config import Config
from cronista.recording.gaps_log import GapsLog, RecordingGap

logger = logging.getLogger(__name__)

REASON = "dave_decrypt_failure"

RecoveryStarter = Callable[[], Awaitable[None]]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class DaveRecovery:
    config: Config
    gaps_log: GapsLog | None = None
    session_id: str = ""
    started_at_iso: str = ""
    started_monotonic: float = 0.0
    channel_id: str = ""
    guild_id: str = ""
    channel_name: str = ""
    loop: asyncio.AbstractEventLoop | None = None
    start_recovery: RecoveryStarter | None = None

    failure_timestamps: list[float] = field(default_factory=list)
    cooldown_until: float = 0.0
    recovery_in_progress: bool = False
    awaiting_validation: bool = False
    validation_event: threading.Event = field(default_factory=threading.Event)
    gap_started_at: str | None = None
    gap_start_ms: int | None = None
    attempts: int = 0
    voice_compromised: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def attach(
        self,
        *,
        gaps_log: GapsLog,
        session_id: str,
        started_at_iso: str,
        started_monotonic: float,
        channel_id: str,
        guild_id: str,
        channel_name: str,
        loop: asyncio.AbstractEventLoop,
        start_recovery: RecoveryStarter,
    ) -> None:
        with self._lock:
            self.gaps_log = gaps_log
            self.session_id = session_id
            self.started_at_iso = started_at_iso
            self.started_monotonic = started_monotonic
            self.channel_id = channel_id
            self.guild_id = guild_id
            self.channel_name = channel_name
            self.loop = loop
            self.start_recovery = start_recovery
            self.failure_timestamps.clear()
            self.cooldown_until = 0.0
            self.recovery_in_progress = False
            self.awaiting_validation = False
            self.validation_event.clear()
            self.gap_started_at = None
            self.gap_start_ms = None
            self.attempts = 0
            self.voice_compromised = False

    def detach(self) -> None:
        with self._lock:
            self.gaps_log = None
            self.start_recovery = None
            self.loop = None
            self.recovery_in_progress = False
            self.awaiting_validation = False
            self.validation_event.set()

    def elapsed_ms(self) -> int:
        if not self.started_monotonic:
            return 0
        return int((time.monotonic() - self.started_monotonic) * 1000)

    def on_decrypt_failure(self) -> None:
        now = time.monotonic()
        with self._lock:
            if self.recovery_in_progress or self.voice_compromised:
                return
            if now < self.cooldown_until:
                logger.debug("[dave_recovery] Falha ignorada (cooldown)")
                return

            window = float(self.config.dave_failure_window_s)
            self.failure_timestamps = [t for t in self.failure_timestamps if now - t <= window]
            self.failure_timestamps.append(now)
            if not self._should_start_recovery_unlocked(now):
                return
            self.recovery_in_progress = True
            self.failure_timestamps.clear()
            self.gap_started_at = _utc_now_iso()
            self.gap_start_ms = self.elapsed_ms()
            self.attempts = 0
            starter = self.start_recovery
            loop = self.loop

        if starter is None or loop is None:
            logger.error("[dave_recovery] Disparo sem starter/loop")
            with self._lock:
                self.recovery_in_progress = False
            return

        logger.warning(
            "[dave_recovery] Limiar atingido — iniciando recuperação session=%s",
            self.session_id,
        )
        asyncio.run_coroutine_threadsafe(starter(), loop)

    def on_decode_success(self) -> None:
        with self._lock:
            self.failure_timestamps.clear()
            if self.awaiting_validation:
                self.validation_event.set()

    def _should_start_recovery_unlocked(self, now: float) -> bool:
        threshold = self.config.dave_failure_threshold
        if len(self.failure_timestamps) < threshold:
            return False
        window = float(self.config.dave_failure_window_s)
        first = self.failure_timestamps[-threshold]
        last = self.failure_timestamps[-1]
        return (last - first) <= window

    def should_start_recovery(self) -> bool:
        """Test helper: evaluate threshold without side effects."""
        now = time.monotonic()
        with self._lock:
            window = float(self.config.dave_failure_window_s)
            recent = [t for t in self.failure_timestamps if now - t <= window]
            if len(recent) < self.config.dave_failure_threshold:
                return False
            return (recent[-1] - recent[-self.config.dave_failure_threshold]) <= window

    def begin_validation_wait(self) -> None:
        with self._lock:
            self.awaiting_validation = True
            self.validation_event.clear()

    def end_validation_wait(self) -> None:
        with self._lock:
            self.awaiting_validation = False

    def wait_for_validation(self, timeout_s: float) -> bool:
        return self.validation_event.wait(timeout=timeout_s)

    def mark_attempt(self) -> int:
        with self._lock:
            self.attempts += 1
            return self.attempts

    def finish_success(self) -> RecordingGap | None:
        with self._lock:
            finished_at = _utc_now_iso()
            end_ms = self.elapsed_ms()
            started_at = self.gap_started_at or finished_at
            start_ms = self.gap_start_ms if self.gap_start_ms is not None else end_ms
            attempts = self.attempts
            gaps_log = self.gaps_log
            session_id = self.session_id
            self.cooldown_until = time.monotonic() + float(self.config.recovery_cooldown_s)
            self.recovery_in_progress = False
            self.awaiting_validation = False
            self.gap_started_at = None
            self.gap_start_ms = None

        entry = RecordingGap(
            session_id=session_id,
            started_at=started_at,
            finished_at=finished_at,
            start_ms=start_ms,
            end_ms=end_ms,
            reason=REASON,
            reconnect_attempts=attempts,
            success=True,
        )
        if gaps_log is not None:
            gaps_log.append(entry)
        return entry

    def finish_failed(self) -> RecordingGap | None:
        with self._lock:
            finished_at = _utc_now_iso()
            end_ms = self.elapsed_ms()
            started_at = self.gap_started_at or finished_at
            start_ms = self.gap_start_ms if self.gap_start_ms is not None else end_ms
            attempts = self.attempts
            gaps_log = self.gaps_log
            session_id = self.session_id
            self.voice_compromised = True
            self.recovery_in_progress = False
            self.awaiting_validation = False
            self.gap_started_at = None
            self.gap_start_ms = None

        entry = RecordingGap(
            session_id=session_id,
            started_at=started_at,
            finished_at=finished_at,
            start_ms=start_ms,
            end_ms=end_ms,
            reason=REASON,
            reconnect_attempts=attempts,
            success=False,
        )
        if gaps_log is not None:
            gaps_log.append(entry)
        return entry

    def gap_duration_s(self, finished_at: str | None = None) -> float:
        started = self.gap_started_at
        if not started:
            return 0.0
        try:
            start_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat((finished_at or _utc_now_iso()).replace("Z", "+00:00"))
            return max(0.0, (end_dt - start_dt).total_seconds())
        except ValueError:
            return 0.0
