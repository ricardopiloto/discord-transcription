"""Pydantic models for HTTP API contracts (v1 + session async)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class TranscribeRequest(BaseModel):
    audio_path: str = Field(min_length=1)
    language: str = Field(min_length=2, max_length=5)


class TranscribeResponse(BaseModel):
    text: str
    language: str
    duration_s: float = Field(ge=0)


class HealthResponse(BaseModel):
    status: str
    model: str
    compute_type: str


class Participant(BaseModel):
    user_id: str = Field(min_length=1)
    display_name: str = ""
    utterance_count: int | None = Field(default=None, ge=0)


class SessionTranscribeRequest(BaseModel):
    session_id: str = Field(min_length=1)
    recordings_path: str = Field(min_length=1)
    speaking_log_path: str = Field(min_length=1)
    participants: list[Participant] = Field(default_factory=list)
    channel_id: str = Field(min_length=1)
    callback_url: HttpUrl


class SessionAcceptedResponse(BaseModel):
    status: Literal["accepted"] = "accepted"
    session_id: str


class SessionStatusResponse(BaseModel):
    status: Literal["in_progress", "done", "failed"]
    processed: int = Field(ge=0)
    total: int = Field(ge=0)
    started_at: str
    finished_at: str | None = None
    utterances_com_texto: int | None = Field(default=None, ge=0)
    output_path: str | None = None
    error: str | None = None
