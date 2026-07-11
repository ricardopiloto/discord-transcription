"""Session domain types."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Participant:
    user_id: str
    display_name: str
    utterance_count: int = 0


@dataclass
class SessionData:
    session_id: str
    guild_id: str
    channel_id: str
    started_at: str
    participants: list[Participant] = field(default_factory=list)
    ended_at: str | None = None
    webhook_failed: bool = False


@dataclass
class SpeakingLogEntry:
    user_id: str
    seq: int
    file: str
    start_ms: int
    end_ms: int
    duration_ms: int
