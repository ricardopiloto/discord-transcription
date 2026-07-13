"""Environment configuration for whisper-service."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

ALLOWED_MODEL_SIZES = frozenset(
    {"tiny", "base", "small", "medium", "large-v2", "large-v3", "large"}
)
ALLOWED_COMPUTE_TYPES = frozenset(
    {"int8", "int8_float16", "int16", "float16", "float32"}
)


def _parse_int(name: str, fallback: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return fallback
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"Variável {name} deve ser um número inteiro") from exc


def _require_choice(name: str, value: str, allowed: frozenset[str]) -> str:
    if value not in allowed:
        allowed_list = ", ".join(sorted(allowed))
        raise ValueError(f"Variável {name} inválida: {value!r}. Valores permitidos: {allowed_list}")
    return value


@dataclass(frozen=True)
class Config:
    model_size: str
    compute_type: str
    host: str
    port: int
    allowed_path_prefix: str


def load_config() -> Config:
    model_size = _require_choice(
        "WHISPER_MODEL_SIZE",
        os.environ.get("WHISPER_MODEL_SIZE", "small"),
        ALLOWED_MODEL_SIZES,
    )
    compute_type = _require_choice(
        "WHISPER_COMPUTE_TYPE",
        os.environ.get("WHISPER_COMPUTE_TYPE", "int8"),
        ALLOWED_COMPUTE_TYPES,
    )
    return Config(
        model_size=model_size,
        compute_type=compute_type,
        host=os.environ.get("WHISPER_HOST", "0.0.0.0"),
        port=_parse_int("WHISPER_PORT", 8008),
        allowed_path_prefix=os.environ.get(
            "WHISPER_ALLOWED_PATH_PREFIX",
            "/opt/apps/cronista/recordings/",
        ),
    )
