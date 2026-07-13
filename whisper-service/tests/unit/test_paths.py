"""Unit tests for path validation."""

from __future__ import annotations

import pytest

from whisper_service.paths import PathValidationError, validate_audio_path


def test_validate_accepts_path_under_prefix(tmp_path):
    prefix = tmp_path / "recordings"
    prefix.mkdir()
    audio = prefix / "session" / "user" / "0001.ogg"
    audio.parent.mkdir(parents=True)
    audio.write_bytes(b"fake")

    resolved = validate_audio_path(str(audio), str(prefix) + "/")
    assert resolved == audio.resolve()


def test_validate_rejects_relative_path(tmp_path):
    with pytest.raises(PathValidationError, match="absoluto"):
        validate_audio_path("relative/path.ogg", str(tmp_path) + "/")


def test_validate_rejects_path_traversal(tmp_path):
    prefix = tmp_path / "recordings"
    prefix.mkdir()
    with pytest.raises(PathValidationError, match="não permitido"):
        validate_audio_path(str(prefix / ".." / "etc" / "passwd"), str(prefix) + "/")


def test_validate_rejects_outside_prefix(tmp_path):
    prefix = tmp_path / "recordings"
    prefix.mkdir()
    outside = tmp_path / "other" / "file.ogg"
    outside.parent.mkdir()
    outside.write_bytes(b"x")
    with pytest.raises(PathValidationError, match="não permitido"):
        validate_audio_path(str(outside), str(prefix) + "/")
