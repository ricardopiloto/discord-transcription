"""Unit tests for DaveRecovery counter / cooldown / gaps close."""

from __future__ import annotations

import time
from pathlib import Path

from cronista.config import Config
from cronista.recording.dave_recovery import DaveRecovery
from cronista.recording.gaps_log import GapsLog


def _config(tmp_path: Path, **overrides) -> Config:
    base = dict(
        discord_token="t",
        recordings_dir=tmp_path,
        utterance_silence_ms=1000,
        auto_end_empty_channel_ms=300_000,
        n8n_webhook_url=None,
        telegram_bot_token=None,
        telegram_chat_id=None,
        telegram_api_base="https://api.telegram.org",
        dave_failure_threshold=3,
        dave_failure_window_s=10,
        reconnect_max_attempts=5,
        reconnect_backoff_s=3,
        recovery_cooldown_s=60,
        reconnect_validate_timeout_s=30,
    )
    base.update(overrides)
    return Config(**base)


def test_threshold_within_window_triggers(tmp_path: Path) -> None:
    recovery = DaveRecovery(_config(tmp_path))
    now = time.monotonic()
    recovery.failure_timestamps = [now - 2, now - 1, now]
    assert recovery.should_start_recovery() is True


def test_failures_outside_window_do_not_trigger(tmp_path: Path) -> None:
    recovery = DaveRecovery(_config(tmp_path, dave_failure_window_s=2))
    now = time.monotonic()
    recovery.failure_timestamps = [now - 20, now - 15, now]
    assert recovery.should_start_recovery() is False


def test_decode_success_clears_failures(tmp_path: Path) -> None:
    recovery = DaveRecovery(_config(tmp_path))
    recovery.failure_timestamps = [time.monotonic()]
    recovery.on_decode_success()
    assert recovery.failure_timestamps == []


def test_finish_success_writes_gap_and_sets_cooldown(tmp_path: Path) -> None:
    session_dir = tmp_path / "sess"
    session_dir.mkdir()
    gaps = GapsLog(session_dir)
    recovery = DaveRecovery(_config(tmp_path, recovery_cooldown_s=30))
    recovery.gaps_log = gaps
    recovery.session_id = "sess"
    recovery.started_monotonic = time.monotonic() - 5
    recovery.gap_started_at = "2026-08-08T12:00:00Z"
    recovery.gap_start_ms = 1000
    recovery.attempts = 2

    entry = recovery.finish_success()
    assert entry is not None
    assert entry.success is True
    assert entry.reconnect_attempts == 2
    assert gaps.count == 1
    assert recovery.cooldown_until > time.monotonic()
    assert recovery.recovery_in_progress is False


def test_finish_failed_marks_compromised(tmp_path: Path) -> None:
    session_dir = tmp_path / "sess"
    session_dir.mkdir()
    gaps = GapsLog(session_dir)
    recovery = DaveRecovery(_config(tmp_path))
    recovery.gaps_log = gaps
    recovery.session_id = "sess"
    recovery.started_monotonic = time.monotonic()
    recovery.gap_started_at = "2026-08-08T12:00:00Z"
    recovery.gap_start_ms = 0
    recovery.attempts = 5

    entry = recovery.finish_failed()
    assert entry is not None
    assert entry.success is False
    assert recovery.voice_compromised is True


def test_cooldown_blocks_on_decrypt_failure_schedule(tmp_path: Path) -> None:
    recovery = DaveRecovery(_config(tmp_path, dave_failure_threshold=1))
    recovery.cooldown_until = time.monotonic() + 60
    recovery.on_decrypt_failure()
    assert recovery.recovery_in_progress is False
    assert recovery.failure_timestamps == []
