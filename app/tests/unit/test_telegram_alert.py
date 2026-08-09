"""Unit tests for Telegram DAVE mid-session alerts."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cronista.config import Config
from cronista.telegram_alert import (
    build_dave_alert_text,
    format_gap_duration,
    normalize_api_base,
    notify_dave_alert,
    send_telegram_message,
)


def _config(
    tmp_path: Path,
    *,
    token: str | None = "123456:ABC-DEF",
    chat_id: str | None = "-100123",
    api_base: str = "https://api.telegram.org",
) -> Config:
    return Config(
        discord_token="t",
        recordings_dir=tmp_path,
        utterance_silence_ms=1000,
        auto_end_empty_channel_ms=300_000,
        n8n_webhook_url=None,
        telegram_bot_token=token,
        telegram_chat_id=chat_id,
        telegram_api_base=api_base,
        dave_failure_threshold=5,
        dave_failure_window_s=10,
        reconnect_max_attempts=5,
        reconnect_backoff_s=3,
        recovery_cooldown_s=60,
        reconnect_validate_timeout_s=30,
    )


def test_format_gap_duration() -> None:
    assert format_gap_duration(45) == "45s"
    assert format_gap_duration(135) == "2m 15s"
    assert format_gap_duration(0) == "0s"


def test_build_templates() -> None:
    detected = build_dave_alert_text(
        event="dave_decrypt_detected",
        channel_name="Mesa",
    )
    assert detected == (
        "⚠️ Cronista: falha de decriptação DAVE detectada no canal Mesa, "
        "tentando reconectar..."
    )

    recovered = build_dave_alert_text(
        event="dave_decrypt_recovered",
        channel_name="Mesa",
        gap_duration_s=135,
    )
    assert recovered == "✅ Reconexão bem-sucedida, gravação retomada após 2m 15s"

    failed = build_dave_alert_text(
        event="dave_decrypt_failed",
        channel_name="Mesa",
        gap_started_at="2026-08-08T22:15:00Z",
        reconnect_attempts=5,
    )
    assert failed == (
        "🔴 Falha ao reconectar após 5 tentativas — "
        "gravação da sessão comprometida a partir de 2026-08-08T22:15:00Z"
    )


def test_normalize_api_base_default() -> None:
    assert normalize_api_base(None) == "https://api.telegram.org"
    assert normalize_api_base("") == "https://api.telegram.org"
    assert normalize_api_base("https://example.com/") == "https://example.com"


@pytest.mark.asyncio
async def test_skips_without_credentials(tmp_path: Path) -> None:
    ok = await notify_dave_alert(
        _config(tmp_path, token=None, chat_id=None),
        event="dave_decrypt_detected",
        channel_name="Mesa",
    )
    assert ok is True


@pytest.mark.asyncio
async def test_skips_without_chat_id(tmp_path: Path) -> None:
    with patch("cronista.telegram_alert.aiohttp.ClientSession") as mock_cls:
        ok = await notify_dave_alert(
            _config(tmp_path, chat_id=None),
            event="dave_decrypt_detected",
            channel_name="Mesa",
        )
    assert ok is True
    mock_cls.assert_not_called()


@pytest.mark.asyncio
async def test_posts_when_configured(tmp_path: Path) -> None:
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"ok": True})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    mock_post = MagicMock(return_value=mock_response)
    mock_session = MagicMock()
    mock_session.post = mock_post
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch("cronista.telegram_alert.aiohttp.ClientSession", return_value=mock_session):
        ok = await notify_dave_alert(
            _config(tmp_path),
            event="dave_decrypt_recovered",
            channel_name="Mesa",
            gap_duration_s=12,
            reconnect_attempts=1,
        )
    assert ok is True
    assert mock_post.call_count == 1
    kwargs = mock_post.call_args.kwargs
    assert kwargs["json"]["chat_id"] == "-100123"
    assert "12s" in kwargs["json"]["text"]


@pytest.mark.asyncio
async def test_retries_three_times_then_false(tmp_path: Path) -> None:
    mock_response = AsyncMock()
    mock_response.status = 500
    mock_response.json = AsyncMock(return_value={"ok": False})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    mock_post = MagicMock(return_value=mock_response)
    mock_session = MagicMock()
    mock_session.post = mock_post
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch("cronista.telegram_alert.aiohttp.ClientSession", return_value=mock_session):
        with patch("cronista.telegram_alert.asyncio.sleep", new_callable=AsyncMock):
            ok = await send_telegram_message(_config(tmp_path), "hello")
    assert ok is False
    assert mock_post.call_count == 3


@pytest.mark.asyncio
async def test_logs_do_not_contain_token(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    token = "123456:SECRET-TOKEN-VALUE"
    mock_response = AsyncMock()
    mock_response.status = 401
    mock_response.json = AsyncMock(return_value={"ok": False, "description": "Unauthorized"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    mock_post = MagicMock(return_value=mock_response)
    mock_session = MagicMock()
    mock_session.post = mock_post
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with caplog.at_level(logging.ERROR, logger="cronista.telegram_alert"):
        with patch("cronista.telegram_alert.aiohttp.ClientSession", return_value=mock_session):
            with patch("cronista.telegram_alert.asyncio.sleep", new_callable=AsyncMock):
                await send_telegram_message(_config(tmp_path, token=token), "hello")

    joined = "\n".join(r.getMessage() for r in caplog.records)
    assert token not in joined
    assert "SECRET-TOKEN-VALUE" not in joined
