"""Unit tests for GapsLog."""

from __future__ import annotations

import json
from pathlib import Path

from cronista.recording.gaps_log import GapsLog, RecordingGap


def test_append_gap_line(tmp_path: Path) -> None:
    session_dir = tmp_path / "20260808-120000"
    session_dir.mkdir()
    log = GapsLog(session_dir)
    entry = RecordingGap(
        session_id="20260808-120000",
        started_at="2026-08-08T12:00:00Z",
        finished_at="2026-08-08T12:01:00Z",
        start_ms=1000,
        end_ms=61000,
        reason="dave_decrypt_failure",
        reconnect_attempts=2,
        success=True,
    )
    log.append(entry)
    assert log.count == 1
    lines = log.file_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["reason"] == "dave_decrypt_failure"
    assert data["success"] is True
    assert data["start_ms"] == 1000
