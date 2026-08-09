"""Direct Telegram Bot API alerts for DAVE recovery mid-session events."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from cronista.config import Config

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
BASE_DELAY_S = 1.0
HTTP_TIMEOUT_S = 15.0
DEFAULT_API_BASE = "https://api.telegram.org"


def format_gap_duration(seconds: float) -> str:
    total_s = max(0, int(round(seconds)))
    if total_s < 60:
        return f"{total_s}s"
    minutes, secs = divmod(total_s, 60)
    return f"{minutes}m {secs}s"


def normalize_api_base(api_base: str | None) -> str:
    base = (api_base or "").strip() or DEFAULT_API_BASE
    return base.rstrip("/")


def redact_token(token: str) -> str:
    if len(token) <= 8:
        return "***"
    return f"{token[:4]}…{token[-2:]}"


def send_message_url(api_base: str, token: str) -> str:
    return f"{normalize_api_base(api_base)}/bot{token}/sendMessage"


def redacted_send_url(api_base: str, token: str) -> str:
    return f"{normalize_api_base(api_base)}/bot{redact_token(token)}/sendMessage"


def build_dave_alert_text(
    *,
    event: str,
    channel_name: str,
    channel_id: str = "",
    gap_started_at: str = "",
    gap_duration_s: float | None = None,
    reconnect_attempts: int | None = None,
) -> str:
    channel = channel_name or channel_id or "?"
    if event == "dave_decrypt_detected":
        return (
            f"⚠️ Cronista: falha de decriptação DAVE detectada no canal {channel}, "
            "tentando reconectar..."
        )
    if event == "dave_decrypt_recovered":
        duration = format_gap_duration(gap_duration_s if gap_duration_s is not None else 0.0)
        return f"✅ Reconexão bem-sucedida, gravação retomada após {duration}"
    if event == "dave_decrypt_failed":
        n = reconnect_attempts if reconnect_attempts is not None else 0
        horario = gap_started_at or "?"
        return (
            f"🔴 Falha ao reconectar após {n} tentativas — "
            f"gravação da sessão comprometida a partir de {horario}"
        )
    return f"Cronista alert: {event}"


def _task_exception_logger(task: asyncio.Task[Any]) -> None:
    try:
        exc = task.exception()
    except asyncio.CancelledError:
        return
    if exc is not None:
        logger.error("[telegram] Task de alerta falhou: %s", exc)


def schedule_dave_alert(config: Config, **kwargs: Any) -> asyncio.Task[bool]:
    """Fire-and-forget DAVE alert (used for detection so reconnect is not delayed)."""
    task = asyncio.create_task(notify_dave_alert(config, **kwargs))
    task.add_done_callback(_task_exception_logger)
    return task


async def notify_dave_alert(
    config: Config,
    *,
    event: str,
    channel_name: str,
    channel_id: str = "",
    gap_started_at: str = "",
    gap_duration_s: float | None = None,
    reconnect_attempts: int | None = None,
) -> bool:
    token = config.telegram_bot_token
    chat_id = config.telegram_chat_id
    if not token or not chat_id:
        logger.warning(
            "[telegram] CRONISTA_TELEGRAM_BOT_TOKEN/CHAT_ID ausentes; alerta mid-session omitido"
        )
        return True

    text = build_dave_alert_text(
        event=event,
        channel_name=channel_name,
        channel_id=channel_id,
        gap_started_at=gap_started_at,
        gap_duration_s=gap_duration_s,
        reconnect_attempts=reconnect_attempts,
    )
    return await send_telegram_message(config, text)


async def send_telegram_message(config: Config, text: str) -> bool:
    token = config.telegram_bot_token
    chat_id = config.telegram_chat_id
    if not token or not chat_id:
        logger.warning(
            "[telegram] CRONISTA_TELEGRAM_BOT_TOKEN/CHAT_ID ausentes; envio omitido"
        )
        return True

    url = send_message_url(config.telegram_api_base, token)
    safe_url = redacted_send_url(config.telegram_api_base, token)
    payload = {"chat_id": chat_id, "text": text}

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            async with aiohttp.ClientSession() as http:
                async with http.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT_S),
                ) as response:
                    body: dict[str, Any] | None = None
                    try:
                        body = await response.json(content_type=None)
                    except Exception:
                        body = None
                    ok_flag = bool(body.get("ok")) if isinstance(body, dict) else response.status < 400
                    if response.status < 400 and ok_flag:
                        return True
                    logger.error(
                        "[telegram] sendMessage tentativa %s/%s falhou: HTTP %s url=%s",
                        attempt,
                        MAX_ATTEMPTS,
                        response.status,
                        safe_url,
                    )
        except aiohttp.ClientError as exc:
            logger.error(
                "[telegram] sendMessage tentativa %s/%s erro: %s url=%s",
                attempt,
                MAX_ATTEMPTS,
                type(exc).__name__,
                safe_url,
            )

        if attempt < MAX_ATTEMPTS:
            await asyncio.sleep(BASE_DELAY_S * (2 ** (attempt - 1)))

    return False
