"""Discord command handlers for !cronista."""

from __future__ import annotations

import asyncio

import discord

from cronista.config import Config
from cronista.end_session import end_active_session
from cronista.session_manager import SessionManager


def _format_duration(ms: int) -> str:
    total_seconds = ms // 1000
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    parts: list[str] = []
    if hours > 0:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)


async def handle_entrar(
    message: discord.Message,
    config: Config,
    session_manager: SessionManager,
) -> None:
    member = message.author
    if not isinstance(member, discord.Member):
        return

    channel = member.voice.channel if member.voice else None
    if channel is None:
        await message.reply("Entre em um canal de voz antes de usar este comando.")
        return

    if session_manager.is_recording:
        await message.reply("Já estou gravando uma sessão. Use `!cronista encerrar` para finalizar.")
        return

    bot_user = message.guild.me if message.guild else None
    if bot_user is None:
        await message.reply("Bot ainda não está pronto. Tente novamente em instantes.")
        return

    voice_client = await channel.connect()
    await channel.guild.change_voice_state(
        channel=channel, self_deaf=False, self_mute=True
    )
    loop = asyncio.get_running_loop()
    try:
        session = await session_manager.start(
            member, voice_client, channel, str(bot_user.id), loop
        )
    except Exception:
        if voice_client.is_connected():
            await voice_client.disconnect(force=True)
        raise

    try:
        await message.reply(
            f"Gravação iniciada — sessão `{session.session_id}` no canal **{channel.name}**."
        )
    except Exception:
        await message.reply(
            f"Gravação iniciada — sessão `{session.session_id}`, "
            "mas não consegui enviar a confirmação completa."
        )


async def handle_encerrar(
    message: discord.Message,
    config: Config,
    session_manager: SessionManager,
) -> None:
    if message.guild is None:
        return

    result = await end_active_session(config, session_manager, message.guild)
    if result is None:
        await message.reply("Não há sessão em andamento.")
        return

    session, webhook_ok = result
    if webhook_ok:
        await message.reply(
            f"Sessão `{session.session_id}` encerrada. Pipeline de transcrição notificado."
        )
    else:
        await message.reply(
            f"Sessão `{session.session_id}` encerrada, mas a notificação ao n8n falhou "
            "(marcado em session.json)."
        )


async def handle_status(message: discord.Message, session_manager: SessionManager) -> None:
    session = session_manager.active_session
    if session is None:
        await message.reply("Nenhuma sessão em andamento.")
        return

    elapsed = _format_duration(session_manager.elapsed_ms())
    participant_count = len(session.participants)
    await message.reply(
        f"**Gravando** — sessão `{session.session_id}`\n"
        f"Duração: {elapsed}\n"
        f"Participantes: {participant_count}"
    )


async def handle_help(message: discord.Message) -> None:
    await message.reply(
        "**Comandos disponíveis:**\n"
        "`!cronista entrar` — entra no canal de voz e inicia a gravação\n"
        "`!cronista encerrar` — finaliza a sessão e notifica o n8n\n"
        "`!cronista status` — mostra status da gravação atual"
    )
