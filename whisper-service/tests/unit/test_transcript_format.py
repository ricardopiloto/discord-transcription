"""Unit tests for transcript line formatting."""

from __future__ import annotations

from whisper_service.transcript_format import (
    SILENCE_MARKER,
    counts_as_com_texto,
    format_timestamp_ms,
    format_transcript_line,
    resolve_display_name,
)


def test_format_timestamp_ms():
    assert format_timestamp_ms(0) == "00:00:00"
    assert format_timestamp_ms(3661000) == "01:01:01"


def test_format_transcript_line_with_text():
    line = format_transcript_line(1500, "Ricardo", "  Olá mundo  ")
    assert line == "[00:00:01] Ricardo: Olá mundo"


def test_format_transcript_line_silence():
    line = format_transcript_line(0, "Alice", "   ")
    assert line == f"[00:00:00] Alice: {SILENCE_MARKER}"


def test_resolve_display_name_fallback():
    assert resolve_display_name("99", {"99": "Bob"}) == "Bob"
    assert resolve_display_name("99", {"99": "  "}) == "99"
    assert resolve_display_name("99", {}) == "99"


def test_counts_as_com_texto():
    assert counts_as_com_texto("hi") is True
    assert counts_as_com_texto("") is False
    assert counts_as_com_texto("  ") is False
