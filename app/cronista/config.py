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
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"Variável {name} deve ser um número inteiro") from exc
    if value < 1:
        raise ValueError(f"Variável {name} deve ser ≥ 1")
    return value


@dataclass(frozen=True)
class Config:
    discord_token: str
    recordings_dir: Path
    utterance_silence_ms: int
    auto_end_empty_channel_ms: int
    n8n_webhook_url: str | None
    alert_webhook_url: str | None
    dave_failure_threshold: int
    dave_failure_window_s: int
    reconnect_max_attempts: int
    reconnect_backoff_s: int
    recovery_cooldown_s: int
    reconnect_validate_timeout_s: int
    prefix: str = "!cronista"


def load_config() -> Config:
    return Config(
        discord_token=_require_env("DISCORD_TOKEN"),
        recordings_dir=Path(os.environ.get("RECORDINGS_DIR", "./recordings")).resolve(),
        utterance_silence_ms=_parse_int("UTTERANCE_SILENCE_MS", 1000),
        auto_end_empty_channel_ms=_parse_int("AUTO_END_EMPTY_CHANNEL_MS", 300_000),
        n8n_webhook_url=os.environ.get("N8N_WEBHOOK_URL") or None,
        alert_webhook_url=os.environ.get("CRONISTA_ALERT_WEBHOOK_URL") or None,
        dave_failure_threshold=_parse_int("CRONISTA_DAVE_FAILURE_THRESHOLD", 5),
        dave_failure_window_s=_parse_int("CRONISTA_DAVE_FAILURE_WINDOW_S", 10),
        reconnect_max_attempts=_parse_int("CRONISTA_RECONNECT_MAX_ATTEMPTS", 5),
        reconnect_backoff_s=_parse_int("CRONISTA_RECONNECT_BACKOFF_S", 3),
        recovery_cooldown_s=_parse_int("CRONISTA_RECOVERY_COOLDOWN_S", 60),
        reconnect_validate_timeout_s=_parse_int("CRONISTA_RECONNECT_VALIDATE_TIMEOUT_S", 30),
    )
