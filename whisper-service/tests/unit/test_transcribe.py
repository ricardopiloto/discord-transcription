"""Unit tests for POST /transcribe."""

from __future__ import annotations

from unittest.mock import patch


def test_transcribe_success(ready_client, recordings_prefix):
    audio = recordings_prefix / "20260712-120000" / "123" / "0001.ogg"
    audio.parent.mkdir(parents=True)
    audio.write_bytes(b"fake-audio")

    with patch("whisper_service.transcriber.transcribe", return_value=("Olá mesa", 4.2)):
        response = ready_client.post(
            "/transcribe",
            json={"audio_path": str(audio), "language": "pt"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["text"] == "Olá mesa"
    assert data["language"] == "pt"
    assert data["duration_s"] == 4.2


def test_transcribe_not_found(ready_client, recordings_prefix):
    missing = recordings_prefix / "missing.ogg"
    response = ready_client.post(
        "/transcribe",
        json={"audio_path": str(missing), "language": "pt"},
    )
    assert response.status_code == 404
    assert "Arquivo não encontrado" in response.json()["detail"]


def test_transcribe_forbidden_path(ready_client, tmp_path):
    outside = tmp_path / "outside.ogg"
    outside.write_bytes(b"x")
    response = ready_client.post(
        "/transcribe",
        json={"audio_path": str(outside), "language": "pt"},
    )
    assert response.status_code == 403


def test_transcribe_model_loading(loading_client, recordings_prefix):
    audio = recordings_prefix / "0001.ogg"
    audio.write_bytes(b"x")
    response = loading_client.post(
        "/transcribe",
        json={"audio_path": str(audio), "language": "pt"},
    )
    assert response.status_code == 503


def test_transcribe_internal_error(ready_client, recordings_prefix):
    audio = recordings_prefix / "0001.ogg"
    audio.write_bytes(b"x")

    with patch("whisper_service.transcriber.transcribe", side_effect=RuntimeError("corrupt")):
        response = ready_client.post(
            "/transcribe",
            json={"audio_path": str(audio), "language": "pt"},
        )
    assert response.status_code == 500
    assert "corrupt" in response.json()["detail"]
