"""In-memory session status store with per-session lock semantics."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class SessionState:
    session_id: str
    status: str  # in_progress | done | failed
    processed: int = 0
    total: int = 0
    started_at: str = field(default_factory=_utc_now_iso)
    finished_at: str | None = None
    utterances_com_texto: int | None = None
    output_path: str | None = None
    error: str | None = None
    channel_id: str = ""
    callback_url: str = ""

    def to_status_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "status": self.status,
            "processed": self.processed,
            "total": self.total,
            "started_at": self.started_at,
        }
        if self.finished_at is not None:
            body["finished_at"] = self.finished_at
        if self.status == "done":
            body["utterances_com_texto"] = self.utterances_com_texto or 0
            body["output_path"] = self.output_path
        if self.status == "failed" and self.error is not None:
            body["error"] = self.error
        return body


class SessionStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, SessionState] = {}

    def get(self, session_id: str) -> SessionState | None:
        with self._lock:
            return self._sessions.get(session_id)

    def try_start(
        self,
        session_id: str,
        *,
        channel_id: str,
        callback_url: str,
    ) -> bool:
        """Register ``in_progress`` unless already running. Returns False → HTTP 409."""
        with self._lock:
            existing = self._sessions.get(session_id)
            if existing is not None and existing.status == "in_progress":
                return False
            self._sessions[session_id] = SessionState(
                session_id=session_id,
                status="in_progress",
                channel_id=channel_id,
                callback_url=callback_url,
            )
            return True

    def set_total(self, session_id: str, total: int) -> None:
        with self._lock:
            state = self._sessions.get(session_id)
            if state is None:
                return
            state.total = total

    def set_processed(self, session_id: str, processed: int) -> None:
        with self._lock:
            state = self._sessions.get(session_id)
            if state is None:
                return
            state.processed = processed

    def mark_done(
        self,
        session_id: str,
        *,
        processed: int,
        total: int,
        utterances_com_texto: int,
        output_path: str,
    ) -> SessionState | None:
        with self._lock:
            state = self._sessions.get(session_id)
            if state is None:
                return None
            state.status = "done"
            state.processed = processed
            state.total = total
            state.utterances_com_texto = utterances_com_texto
            state.output_path = output_path
            state.error = None
            state.finished_at = _utc_now_iso()
            return state

    def mark_failed(
        self,
        session_id: str,
        *,
        error: str,
        processed: int,
        total: int,
    ) -> SessionState | None:
        with self._lock:
            state = self._sessions.get(session_id)
            if state is None:
                return None
            state.status = "failed"
            state.error = error
            state.processed = processed
            state.total = total
            state.finished_at = _utc_now_iso()
            state.output_path = None
            state.utterances_com_texto = None
            return state


_store = SessionStore()


def get_store() -> SessionStore:
    return _store


def reset_store_for_tests() -> None:
    global _store
    _store = SessionStore()
