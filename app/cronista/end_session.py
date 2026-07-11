"""Shared session end logic."""

from __future__ import annotations

import logging

import discord

from cronista.config import Config
from cronista.recording.storage import write_session_json
from cronista.session import SessionData
from cronista.session_manager import SessionManager
from cronista.webhook import notify_session_ended

logger = logging.getLogger(__name__)


async def end_active_session(
    config: Config,
    session_manager: SessionManager,
    guild: discord.Guild,
) -> tuple[SessionData, bool] | None:
    if not session_manager.is_recording:
        return None

    session = await session_manager.end()
    if session is None:
        return None

    if guild.voice_client:
        await guild.voice_client.disconnect(force=True)

    webhook_ok = await notify_session_ended(config, session)
    if not webhook_ok:
        session.webhook_failed = True
        session_dir = config.recordings_dir / session.session_id
        await write_session_json(session_dir, session)

    logger.info(
        "[session] Encerrada %s — webhook %s",
        session.session_id,
        "ok" if webhook_ok else "falhou",
    )
    return session, webhook_ok
