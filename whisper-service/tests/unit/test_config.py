"""Unit tests for config loading and validation."""

from __future__ import annotations

import pytest

from whisper_service.config import ALLOWED_COMPUTE_TYPES, ALLOWED_MODEL_SIZES, load_config


def test_load_config_defaults(monkeypatch):
    monkeypatch.delenv("WHISPER_MODEL_SIZE", raising=False)
    monkeypatch.delenv("WHISPER_COMPUTE_TYPE", raising=False)
    monkeypatch.delenv("WHISPER_HOST", raising=False)
    monkeypatch.delenv("WHISPER_PORT", raising=False)
    monkeypatch.delenv("WHISPER_ALLOWED_PATH_PREFIX", raising=False)

    cfg = load_config()
    assert cfg.model_size == "small"
    assert cfg.compute_type == "int8"
    assert cfg.host == "0.0.0.0"
    assert cfg.port == 8008
    assert cfg.allowed_path_prefix == "/opt/apps/cronista/recordings/"


def test_invalid_model_size_raises(monkeypatch):
    monkeypatch.setenv("WHISPER_MODEL_SIZE", "invalid-model")
    with pytest.raises(ValueError, match="WHISPER_MODEL_SIZE"):
        load_config()


def test_invalid_compute_type_raises(monkeypatch):
    monkeypatch.setenv("WHISPER_COMPUTE_TYPE", "invalid")
    with pytest.raises(ValueError, match="WHISPER_COMPUTE_TYPE"):
        load_config()


def test_allowed_sets_cover_defaults():
    assert "small" in ALLOWED_MODEL_SIZES
    assert "int8" in ALLOWED_COMPUTE_TYPES
