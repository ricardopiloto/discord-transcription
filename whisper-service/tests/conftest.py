"""Shared pytest fixtures for whisper-service."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def recordings_prefix(tmp_path, monkeypatch):
    prefix = tmp_path / "recordings"
    prefix.mkdir()
    monkeypatch.setenv("WHISPER_ALLOWED_PATH_PREFIX", str(prefix) + "/")
    monkeypatch.setenv("WHISPER_MODEL_SIZE", "small")
    monkeypatch.setenv("WHISPER_COMPUTE_TYPE", "int8")
    return prefix


@pytest.fixture
def ready_client(recordings_prefix):
    with patch("whisper_service.transcriber.load"), patch(
        "whisper_service.transcriber.is_ready_state", return_value=True
    ):
        from whisper_service.main import app

        with TestClient(app) as client:
            yield client


@pytest.fixture
def loading_client(recordings_prefix):
    with patch("whisper_service.transcriber.load"), patch(
        "whisper_service.transcriber.is_ready_state", return_value=False
    ):
        from whisper_service.main import app

        with TestClient(app) as client:
            yield client
