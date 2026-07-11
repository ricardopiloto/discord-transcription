"""Unit tests for storage helpers."""

from datetime import datetime, timezone

import pytest

from cronista.recording.storage import format_session_id, format_utterance_filename


def test_format_session_id_matches_pattern() -> None:
    when = datetime(2026, 7, 10, 22, 1, 5, tzinfo=timezone.utc)
    session_id = format_session_id(when)
    assert session_id == "20260710-220105"
    assert len(session_id) == 15


def test_format_utterance_filename_zero_pads() -> None:
    assert format_utterance_filename(1) == "0001.ogg"
    assert format_utterance_filename(42) == "0042.ogg"
    assert format_utterance_filename(9999) == "9999.ogg"
