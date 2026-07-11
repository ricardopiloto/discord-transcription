"""n8n webhook notification with retry."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

import aiohttp

from cronista.config import Config
from cronista.recording.storage import session_to_dict
from cronista.session import SessionData

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
BASE_DELAY_S = 1.0


def build_payload(session: SessionData, recordings_dir: Path) -> dict[str, Any]:
    if session.ended_at is None:
        raise ValueError("Sessão sem ended_at não pode ser notificada")

    session_dir = recordings_dir / session.session_id
    return {
        "session_id": session.session_id,
        "guild_id": session.guild_id,
        "channel_id": session.channel_id,
        "started_at": session.started_at,
        "ended_at": session.ended_at,
        "recordings_path": str(session_dir),
        "session_json_path": str(session_dir / "session.json"),
        "speaking_log_path": str(session_dir / "speaking_log.jsonl"),
        "participants": session_to_dict(session)["participants"],
    }


async def notify_session_ended(config: Config, session: SessionData) -> bool:
    url = config.n8n_webhook_url
    if not url:
        logger.warning("[webhook] N8N_WEBHOOK_URL não configurada; notificação ignorada")
        return True

    payload = build_payload(session, config.recordings_dir)

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            async with aiohttp.ClientSession() as http:
                async with http.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status < 400:
                        return True
                    logger.error(
                        "[webhook] Tentativa %s/%s falhou: HTTP %s",
                        attempt,
                        MAX_ATTEMPTS,
                        response.status,
                    )
        except aiohttp.ClientError as exc:
            logger.error("[webhook] Tentativa %s/%s erro: %s", attempt, MAX_ATTEMPTS, exc)

        if attempt < MAX_ATTEMPTS:
            await asyncio.sleep(BASE_DELAY_S * (2 ** (attempt - 1)))

    return False
