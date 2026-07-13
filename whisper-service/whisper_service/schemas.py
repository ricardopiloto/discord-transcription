"""Pydantic models for HTTP API contracts."""

from __future__ import annotations

from pydantic import BaseModel, Field


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
