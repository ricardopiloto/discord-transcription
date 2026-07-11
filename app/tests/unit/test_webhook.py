"""Unit tests for webhook retry logic."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cronista.config import Config
from cronista.session import SessionData
from cronista.webhook import notify_session_ended

BASE_SESSION = SessionData(
    session_id="20260710-220105",
    guild_id="guild1",
    channel_id="channel1",
    started_at="2026-07-10T22:01:05.000Z",
    ended_at="2026-07-10T23:00:00.000Z",
    participants=[],
)


def _config(tmp_path: Path) -> Config:
    return Config(
        discord_token="test",
        recordings_dir=tmp_path,
        utterance_silence_ms=1000,
        auto_end_empty_channel_ms=300_000,
        n8n_webhook_url="https://example.com/webhook",
    )


@pytest.mark.asyncio
async def test_webhook_retries_three_times_on_failure(tmp_path: Path) -> None:
    config = _config(tmp_path)
    mock_response = AsyncMock()
    mock_response.status = 500
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    mock_post = MagicMock(return_value=mock_response)
    mock_session = MagicMock()
    mock_session.post = mock_post
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch("cronista.webhook.aiohttp.ClientSession", return_value=mock_session):
        with patch("cronista.webhook.asyncio.sleep", new_callable=AsyncMock):
            ok = await notify_session_ended(config, BASE_SESSION)

    assert ok is False
    assert mock_post.call_count == 3


@pytest.mark.asyncio
async def test_webhook_returns_true_on_first_success(tmp_path: Path) -> None:
    config = _config(tmp_path)
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
        ok = await notify_session_ended(config, BASE_SESSION)

    assert ok is True
    assert mock_post.call_count == 1


@pytest.mark.asyncio
async def test_webhook_skips_when_url_not_configured(tmp_path: Path) -> None:
    config = Config(
        discord_token="test",
        recordings_dir=tmp_path,
        utterance_silence_ms=1000,
        auto_end_empty_channel_ms=300_000,
        n8n_webhook_url=None,
    )
    ok = await notify_session_ended(config, BASE_SESSION)
    assert ok is True
