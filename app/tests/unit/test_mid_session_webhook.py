"""Unit tests for mid-session alert webhook."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cronista.config import Config
from cronista.webhook import build_mid_session_alert, notify_mid_session_alert


def _config(tmp_path: Path, *, alert_url: str | None) -> Config:
    return Config(
        discord_token="t",
        recordings_dir=tmp_path,
        utterance_silence_ms=1000,
        auto_end_empty_channel_ms=300_000,
        n8n_webhook_url=None,
        alert_webhook_url=alert_url,
        dave_failure_threshold=5,
        dave_failure_window_s=10,
        reconnect_max_attempts=5,
        reconnect_backoff_s=3,
        recovery_cooldown_s=60,
        reconnect_validate_timeout_s=30,
    )


def test_build_detected_message() -> None:
    body = build_mid_session_alert(
        event="dave_decrypt_detected",
        session_id="s1",
        channel_id="c1",
        guild_id="g1",
        channel_name="Mesa",
        gap_started_at="2026-08-08T12:00:00Z",
    )
    assert body["event"] == "dave_decrypt_detected"
    assert "Mesa" in body["message"]


@pytest.mark.asyncio
async def test_mid_session_skips_without_url(tmp_path: Path) -> None:
    ok = await notify_mid_session_alert(
        _config(tmp_path, alert_url=None),
        {"event": "dave_decrypt_detected", "message": "x"},
    )
    assert ok is True


@pytest.mark.asyncio
async def test_mid_session_posts_when_configured(tmp_path: Path) -> None:
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    mock_post = MagicMock(return_value=mock_response)
    mock_session = MagicMock()
    mock_session.post = mock_post
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch("cronista.webhook.aiohttp.ClientSession", return_value=mock_session):
        ok = await notify_mid_session_alert(
            _config(tmp_path, alert_url="https://example.com/alert"),
            build_mid_session_alert(
                event="dave_decrypt_recovered",
                session_id="s1",
                channel_id="c1",
                guild_id="g1",
                channel_name="Mesa",
                gap_started_at="2026-08-08T12:00:00Z",
                gap_duration_s=12,
                reconnect_attempts=1,
                success=True,
            ),
        )
    assert ok is True
    assert mock_post.call_count == 1
