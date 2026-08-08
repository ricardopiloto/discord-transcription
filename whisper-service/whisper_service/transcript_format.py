"""Format lines for session ``transcricao.txt``."""

from __future__ import annotations

SILENCE_MARKER = "(silêncio)"


def format_timestamp_ms(start_ms: int) -> str:
    """Convert relative start_ms to ``HH:MM:SS`` (hours may exceed 24)."""
    total_s = max(0, int(start_ms)) // 1000
    hours = total_s // 3600
    minutes = (total_s % 3600) // 60
    seconds = total_s % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def resolve_display_name(user_id: str, name_by_id: dict[str, str]) -> str:
    """Return display name or fall back to ``user_id``."""
    name = (name_by_id.get(user_id) or "").strip()
    return name if name else user_id


def format_transcript_line(start_ms: int, display_name: str, text: str) -> str:
    """Build ``[HH:MM:SS] Nome: texto`` or silence marker when text empty."""
    cleaned = (text or "").strip()
    body = cleaned if cleaned else SILENCE_MARKER
    return f"[{format_timestamp_ms(start_ms)}] {display_name}: {body}"


def counts_as_com_texto(text: str) -> bool:
    """True when transcribed text is non-empty (silence marker does not count)."""
    cleaned = (text or "").strip()
    return bool(cleaned)
