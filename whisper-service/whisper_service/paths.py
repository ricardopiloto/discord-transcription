"""Filesystem path validation for transcribe and session requests."""

from __future__ import annotations

from pathlib import Path


class PathValidationError(Exception):
    """Raised when a path fails security or format checks."""


def validate_allowed_path(path: str, allowed_prefix: str) -> Path:
    """Resolve and ensure ``path`` is absolute and under ``allowed_prefix``."""
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


def validate_audio_path(path: str, allowed_prefix: str) -> Path:
    """Alias for utterance audio paths (v1 contract)."""
    return validate_allowed_path(path, allowed_prefix)


def validate_session_path(path: str, allowed_prefix: str) -> Path:
    """Validate ``recordings_path`` / ``speaking_log_path`` under the allowed prefix."""
    return validate_allowed_path(path, allowed_prefix)
