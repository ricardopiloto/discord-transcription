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
) -> tuple[SessionData, bool, int] | None:
    if not session_manager.is_recording:
        return None

    gap_count = session_manager.gap_count()
    gaps_path = session_manager.recording_gaps_path()

    session = await session_manager.end()
    if session is None:
        return None

    if guild.voice_client:
        await guild.voice_client.disconnect(force=True)

    webhook_ok = await notify_session_ended(
        config,
        session,
        gap_count=gap_count,
        recording_gaps_path=gaps_path,
    )
    if not webhook_ok:
        session.webhook_failed = True
        session_dir = config.recordings_dir / session.session_id
        await write_session_json(session_dir, session)

    logger.info(
        "[session] Encerrada %s — webhook %s — gaps=%s",
        session.session_id,
        "ok" if webhook_ok else "falhou",
        gap_count,
    )
    return session, webhook_ok, gap_count
