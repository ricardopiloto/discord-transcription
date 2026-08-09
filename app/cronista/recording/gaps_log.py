"""Append-only recording gaps log (JSON Lines)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class RecordingGap:
    session_id: str
    started_at: str
    finished_at: str
    start_ms: int
    end_ms: int
    reason: str
    reconnect_attempts: int
    success: bool


class GapsLog:
    def __init__(self, session_dir: Path) -> None:
        self.file_path = session_dir / "recording_gaps.jsonl"
        self.count = 0

    def append(self, entry: RecordingGap) -> None:
        line = json.dumps(asdict(entry), ensure_ascii=False) + "\n"
        with self.file_path.open("a", encoding="utf-8") as handle:
            handle.write(line)
        self.count += 1

    def path_str(self) -> str:
        return str(self.file_path.resolve())
