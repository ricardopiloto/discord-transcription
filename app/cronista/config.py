"""Environment configuration for Cronista."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"Variável de ambiente obrigatória ausente: {name}")
    return value


def _parse_int(name: str, fallback: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return fallback
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"Variável {name} deve ser um número inteiro") from exc


@dataclass(frozen=True)
class Config:
    discord_token: str
    recordings_dir: Path
    utterance_silence_ms: int
    auto_end_empty_channel_ms: int
    n8n_webhook_url: str | None
    prefix: str = "!cronista"


def load_config() -> Config:
    return Config(
        discord_token=_require_env("DISCORD_TOKEN"),
        recordings_dir=Path(os.environ.get("RECORDINGS_DIR", "./recordings")).resolve(),
        utterance_silence_ms=_parse_int("UTTERANCE_SILENCE_MS", 1000),
        auto_end_empty_channel_ms=_parse_int("AUTO_END_EMPTY_CHANNEL_MS", 300_000),
        n8n_webhook_url=os.environ.get("N8N_WEBHOOK_URL") or None,
    )
