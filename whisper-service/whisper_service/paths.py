"""Filesystem path validation for transcribe requests."""

from __future__ import annotations

from pathlib import Path


class PathValidationError(Exception):
    """Raised when audio_path fails security or format checks."""


def validate_audio_path(path: str, allowed_prefix: str) -> Path:
    if not path or not path.strip():
        raise PathValidationError("Caminho vazio")

    candidate = Path(path)
    if not candidate.is_absolute():
        raise PathValidationError(f"Caminho deve ser absoluto: {path}")

    if ".." in path.split("/"):
        raise PathValidationError(f"Caminho não permitido: {path}")

    resolved = candidate.resolve()
    prefix = Path(allowed_prefix).resolve()
    try:
        resolved.relative_to(prefix)
    except ValueError as exc:
        raise PathValidationError(f"Caminho não permitido: {path}") from exc

    return resolved
