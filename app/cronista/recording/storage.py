"""Session file storage helpers."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cronista.session import SessionData


def format_session_id(when: datetime) -> str:
    return when.strftime("%Y%m%d-%H%M%S")


def format_utterance_filename(seq: int) -> str:
    return f"{seq:04d}.ogg"


async def ensure_session_dir(base_dir: Path, session_id: str) -> Path:
    session_dir = base_dir / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


async def ensure_user_dir(session_dir: Path, user_id: str) -> Path:
    user_dir = session_dir / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def session_to_dict(session: SessionData) -> dict[str, Any]:
    data: dict[str, Any] = {
        "session_id": session.session_id,
        "guild_id": session.guild_id,
        "channel_id": session.channel_id,
        "started_at": session.started_at,
        "participants": [
            {
                "user_id": p.user_id,
                "display_name": p.display_name,
                "utterance_count": p.utterance_count,
            }
            for p in session.participants
        ],
    }
    if session.ended_at is not None:
        data["ended_at"] = session.ended_at
    if session.webhook_failed:
        data["webhook_failed"] = True
    return data


async def write_session_json(session_dir: Path, session: SessionData) -> Path:
    file_path = session_dir / "session.json"
    content = json.dumps(session_to_dict(session), ensure_ascii=False, indent=2) + "\n"
    file_path.write_text(content, encoding="utf-8")
    return file_path
