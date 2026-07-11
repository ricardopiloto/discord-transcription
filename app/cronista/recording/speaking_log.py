"""Append-only speaking log (JSON Lines)."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from cronista.session import SpeakingLogEntry


class SpeakingLog:
    def __init__(self, session_dir: Path) -> None:
        self.file_path = session_dir / "speaking_log.jsonl"

    async def append(self, entry: SpeakingLogEntry) -> None:
        line = json.dumps(asdict(entry), ensure_ascii=False) + "\n"
        with self.file_path.open("a", encoding="utf-8") as handle:
            handle.write(line)
