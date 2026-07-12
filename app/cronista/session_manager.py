"""Session lifecycle management."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

import discord

from cronista.config import Config
from cronista.recording.sink import IncrementalUtteranceSink
from cronista.recording.speaking_log import SpeakingLog
from cronista.recording.storage import ensure_session_dir, ensure_user_dir, format_session_id, write_session_json
from cronista.session import Participant, SessionData

logger = logging.getLogger(__name__)


class SessionManager:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.session: SessionData | None = None
        self.session_dir = None
        self.speaking_log: SpeakingLog | None = None
        self.started_monotonic = 0.0
        self.voice_client: discord.VoiceClient | None = None
        self.sink: IncrementalUtteranceSink | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    @property
    def is_recording(self) -> bool:
        return self.session is not None

    @property
    def active_session(self) -> SessionData | None:
        return self.session

    def elapsed_ms(self) -> int:
        if not self.started_monotonic:
            return 0
        return int((time.monotonic() - self.started_monotonic) * 1000)

    async def start(
        self,
        member: discord.Member,
        voice_client: discord.VoiceClient,
        channel: discord.VoiceChannel,
        bot_user_id: str,
        loop: asyncio.AbstractEventLoop,
    ) -> SessionData:
        if self.session is not None:
            raise RuntimeError("Já existe uma sessão em andamento")

        now = datetime.now(timezone.utc)
        session_id = format_session_id(now)

        self.session_dir = await ensure_session_dir(self.config.recordings_dir, session_id)
        self.speaking_log = SpeakingLog(self.session_dir)
        self.started_monotonic = time.monotonic()
        self.voice_client = voice_client
        self._loop = loop

        self.session = SessionData(
            session_id=session_id,
            guild_id=str(member.guild.id),
            channel_id=str(channel.id),
            started_at=now.isoformat().replace("+00:00", "Z"),
        )
        await write_session_json(self.session_dir, self.session)

        def recording_finished(exception: Exception | None) -> None:
            if exception:
                logger.error("[session] Recording error: %s", exception)

        self.sink = IncrementalUtteranceSink(
            session_dir=self.session_dir,
            session_started_monotonic=self.started_monotonic,
            speaking_log=self.speaking_log,
            utterance_silence_ms=self.config.utterance_silence_ms,
            bot_user_id=bot_user_id,
            guild=member.guild,
            voice_channel=channel,
            loop=loop,
            on_participant=self.register_participant,
            on_utterance_complete=self.increment_utterance_count,
        )
        try:
            self.sink.init(voice_client)
            voice_client.start_recording(self.sink, recording_finished)
        except Exception:
            self._reset()
            raise

        await self._register_channel_members(channel)

        logger.info("[session] Iniciada %s no canal %s", session_id, channel.name)
        return self.session

    async def end(self) -> SessionData | None:
        if self.session is None or self.session_dir is None:
            return None

        if self.voice_client and self.voice_client.is_recording():
            self.voice_client.stop_recording()

        if self.sink is not None:
            await self.sink.flush_all()

        ended_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        self.session.ended_at = ended_at

        try:
            await write_session_json(self.session_dir, self.session)
        except OSError as exc:
            logger.error("[session] Falha ao persistir session.json no encerramento: %s", exc)

        finished = self.session
        self._reset()
        return finished

    def _reset(self) -> None:
        self.session = None
        self.session_dir = None
        self.speaking_log = None
        self.voice_client = None
        self.sink = None
        self.started_monotonic = 0.0
        self._loop = None

    async def register_participant(self, user_id: str, display_name: str) -> None:
        if self.session is None or self.session_dir is None:
            return

        if any(p.user_id == user_id for p in self.session.participants):
            participant = next(p for p in self.session.participants if p.user_id == user_id)
            if participant.display_name != display_name and not display_name.startswith("user-"):
                participant.display_name = display_name
                try:
                    await write_session_json(self.session_dir, self.session)
                except OSError as exc:
                    logger.error("[session] Falha ao atualizar nome de %s: %s", user_id, exc)
            return

        self.session.participants.append(
            Participant(user_id=user_id, display_name=display_name, utterance_count=0)
        )
        try:
            await ensure_user_dir(self.session_dir, user_id)
            await write_session_json(self.session_dir, self.session)
            logger.info("[session] Participante registrado: %s (%s)", display_name, user_id)
        except OSError as exc:
            logger.error("[session] Falha ao registrar participante %s: %s", user_id, exc)

    async def register_voice_channel_member(self, member: discord.Member) -> None:
        if member.bot:
            return
        await self.register_participant(str(member.id), member.display_name or member.name)

    async def _register_channel_members(self, channel: discord.VoiceChannel) -> None:
        for member in channel.members:
            await self.register_voice_channel_member(member)

    async def increment_utterance_count(self, user_id: str) -> None:
        if self.session is None or self.session_dir is None:
            return

        participant = next((p for p in self.session.participants if p.user_id == user_id), None)
        if participant is None:
            return

        participant.utterance_count += 1
        try:
            await write_session_json(self.session_dir, self.session)
        except OSError as exc:
            logger.error("[session] Falha ao incrementar utterance_count de %s: %s", user_id, exc)
