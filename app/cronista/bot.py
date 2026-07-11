"""Discord bot client and event wiring."""

from __future__ import annotations

import asyncio
import logging

import discord

from cronista.commands import handle_encerrar, handle_entrar, handle_help, handle_status
from cronista.config import Config
from cronista.end_session import end_active_session
from cronista.session_manager import SessionManager

logger = logging.getLogger(__name__)


def create_bot(config: Config, session_manager: SessionManager) -> discord.Client:
    intents = discord.Intents.default()
    intents.guilds = True
    intents.voice_states = True
    intents.message_content = True

    client = discord.Client(intents=intents)
    empty_channel_tasks: dict[str, asyncio.Task[None]] = {}

    def _cancel_auto_end(guild_id: str) -> None:
        task = empty_channel_tasks.pop(guild_id, None)
        if task is not None:
            task.cancel()

    def _count_humans(channel: discord.VoiceChannel) -> int:
        return sum(1 for m in channel.members if not m.bot)

    def _schedule_auto_end(guild: discord.Guild) -> None:
        session = session_manager.active_session
        if session is None or str(guild.id) != session.guild_id:
            return

        channel = guild.get_channel(int(session.channel_id))
        if not isinstance(channel, discord.VoiceChannel):
            return

        if _count_humans(channel) > 0:
            _cancel_auto_end(str(guild.id))
            return

        guild_id = str(guild.id)
        _cancel_auto_end(guild_id)

        async def _auto_end() -> None:
            try:
                await asyncio.sleep(config.auto_end_empty_channel_ms / 1000.0)
                current = session_manager.active_session
                if current is None or current.session_id != session.session_id:
                    return
                ch = guild.get_channel(int(current.channel_id))
                if isinstance(ch, discord.VoiceChannel) and _count_humans(ch) == 0:
                    logger.info(
                        "[session] Canal vazio por %sms — encerrando %s",
                        config.auto_end_empty_channel_ms,
                        current.session_id,
                    )
                    await end_active_session(config, session_manager, guild)
            except asyncio.CancelledError:
                pass

        empty_channel_tasks[guild_id] = asyncio.create_task(_auto_end())

    @client.event
    async def on_ready() -> None:
        logger.info("[bot] Conectado como %s", client.user)

    @client.event
    async def on_message(message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return

        content = message.content.strip()
        lower = content.lower()
        prefix = config.prefix.lower()

        if not lower.startswith(prefix):
            return

        sub = lower[len(prefix) :].strip()
        try:
            if sub == "entrar":
                await handle_entrar(message, config, session_manager)
            elif sub == "encerrar":
                await handle_encerrar(message, config, session_manager)
            elif sub == "status":
                await handle_status(message, session_manager)
            elif sub in ("", "help"):
                await handle_help(message)
        except Exception:
            logger.exception("[bot] Erro ao processar comando")
            await message.reply("Ocorreu um erro ao processar o comando.")

    @client.event
    async def on_voice_state_update(
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        session = session_manager.active_session
        if session is None:
            return

        if str(member.guild.id) != session.guild_id:
            return

        if before.channel and str(before.channel.id) == session.channel_id:
            _schedule_auto_end(member.guild)
        if after.channel and str(after.channel.id) == session.channel_id:
            await session_manager.register_voice_channel_member(member)
            _schedule_auto_end(member.guild)

    return client
