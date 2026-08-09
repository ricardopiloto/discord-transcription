"""Session lifecycle management + DAVE full reconnect recovery."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

import discord

from cronista.config import Config
from cronista.recording.dave_hooks import install_dave_decrypt_hooks
from cronista.recording.dave_recovery import DaveRecovery
from cronista.recording.gaps_log import GapsLog
from cronista.recording.sink import IncrementalUtteranceSink
from cronista.recording.speaking_log import SpeakingLog
from cronista.recording.storage import ensure_session_dir, ensure_user_dir, format_session_id, write_session_json
from cronista.session import Participant, SessionData
from cronista.telegram_alert import notify_dave_alert, schedule_dave_alert

logger = logging.getLogger(__name__)


class SessionManager:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.session: SessionData | None = None
        self.session_dir = None
        self.speaking_log: SpeakingLog | None = None
        self.gaps_log: GapsLog | None = None
        self.dave_recovery = DaveRecovery(config)
        self.started_monotonic = 0.0
        self.voice_client: discord.VoiceClient | None = None
        self.sink: IncrementalUtteranceSink | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._voice_channel: discord.VoiceChannel | None = None
        self._bot_user_id: str = ""
        self._guild: discord.Guild | None = None
        self._hooks_installed = False

    @property
    def is_recording(self) -> bool:
        return self.session is not None

    @property
    def active_session(self) -> SessionData | None:
        return self.session

    def gap_count(self) -> int:
        return self.gaps_log.count if self.gaps_log is not None else 0

    def recording_gaps_path(self) -> str | None:
        if self.gaps_log is None or self.gaps_log.count <= 0:
            return None
        return self.gaps_log.path_str()

    def elapsed_ms(self) -> int:
        if not self.started_monotonic:
            return 0
        return int((time.monotonic() - self.started_monotonic) * 1000)

    def ensure_hooks(self) -> None:
        if self._hooks_installed:
            return
        install_dave_decrypt_hooks(self.dave_recovery.on_decrypt_failure)
        self._hooks_installed = True

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

        self.ensure_hooks()

        now = datetime.now(timezone.utc)
        session_id = format_session_id(now)

        self.session_dir = await ensure_session_dir(self.config.recordings_dir, session_id)
        self.speaking_log = SpeakingLog(self.session_dir)
        self.gaps_log = GapsLog(self.session_dir)
        self.started_monotonic = time.monotonic()
        self.voice_client = voice_client
        self._loop = loop
        self._voice_channel = channel
        self._bot_user_id = bot_user_id
        self._guild = member.guild

        started_at = now.isoformat().replace("+00:00", "Z")
        self.session = SessionData(
            session_id=session_id,
            guild_id=str(member.guild.id),
            channel_id=str(channel.id),
            started_at=started_at,
        )
        await write_session_json(self.session_dir, self.session)

        self.dave_recovery.attach(
            gaps_log=self.gaps_log,
            session_id=session_id,
            started_at_iso=started_at,
            started_monotonic=self.started_monotonic,
            channel_id=str(channel.id),
            guild_id=str(member.guild.id),
            channel_name=channel.name,
            loop=loop,
            start_recovery=self._run_dave_recovery,
        )

        await self._start_recording_pipeline(member.guild, channel, bot_user_id, loop)
        await self._register_channel_members(channel)

        logger.info("[session] Iniciada %s no canal %s", session_id, channel.name)
        return self.session

    async def _start_recording_pipeline(
        self,
        guild: discord.Guild,
        channel: discord.VoiceChannel,
        bot_user_id: str,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        if self.session_dir is None or self.speaking_log is None or self.voice_client is None:
            raise RuntimeError("Sessão não inicializada")

        recording_finished = self._make_recording_finished_callback()
        self.sink = IncrementalUtteranceSink(
            session_dir=self.session_dir,
            session_started_monotonic=self.started_monotonic,
            speaking_log=self.speaking_log,
            utterance_silence_ms=self.config.utterance_silence_ms,
            bot_user_id=bot_user_id,
            guild=guild,
            voice_channel=channel,
            loop=loop,
            on_participant=self.register_participant,
            on_utterance_complete=self.increment_utterance_count,
            on_decode_success=self.dave_recovery.on_decode_success,
        )
        self.sink.init(self.voice_client)
        await self._wait_dave_warmup(self.voice_client)
        self.voice_client.start_recording(self.sink, recording_finished)

    async def end(self) -> SessionData | None:
        if self.session is None or self.session_dir is None:
            return None

        if self.voice_client and self.voice_client.is_connected() and self.voice_client.is_recording():
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

    async def reconnect_voice_full(self) -> bool:
        """Full disconnect + connect + warmup + start_recording. Same session_id/dirs."""
        channel = self._voice_channel
        guild = self._guild
        loop = self._loop
        if channel is None or guild is None or loop is None or self.session is None:
            return False

        if self.sink is not None:
            await self.sink.flush_all()

        old_vc = self.voice_client
        if old_vc is not None:
            try:
                if old_vc.is_recording():
                    old_vc.stop_recording()
            except Exception as exc:
                logger.warning("[session] stop_recording durante reconnect: %s", exc)
            try:
                if old_vc.is_connected():
                    await old_vc.disconnect(force=True)
            except Exception as exc:
                logger.warning("[session] disconnect durante reconnect: %s", exc)

        self.voice_client = None
        self.sink = None

        try:
            voice_client = await channel.connect()
            await guild.change_voice_state(channel=channel, self_deaf=False, self_mute=True)
            self.voice_client = voice_client
            await self._start_recording_pipeline(guild, channel, self._bot_user_id, loop)
            return True
        except Exception:
            logger.exception("[session] Falha no reconnect_voice_full")
            self.voice_client = None
            self.sink = None
            return False

    async def _run_dave_recovery(self) -> None:
        recovery = self.dave_recovery
        gap_started = recovery.gap_started_at or ""
        # Detection alert must not delay reconnect (Telegram retries run in parallel).
        schedule_dave_alert(
            self.config,
            event="dave_decrypt_detected",
            channel_name=recovery.channel_name,
            channel_id=recovery.channel_id,
            gap_started_at=gap_started,
        )

        max_attempts = self.config.reconnect_max_attempts
        backoff_base = float(self.config.reconnect_backoff_s)
        validate_timeout = float(self.config.reconnect_validate_timeout_s)

        for attempt in range(1, max_attempts + 1):
            recovery.attempts = attempt
            if attempt > 1:
                delay = backoff_base * (attempt - 1)
                logger.info(
                    "[dave_recovery] Backoff %.1fs antes da tentativa %s/%s",
                    delay,
                    attempt,
                    max_attempts,
                )
                await asyncio.sleep(delay)

            connected = await self.reconnect_voice_full()
            if not connected:
                logger.warning("[dave_recovery] Tentativa %s: connect falhou", attempt)
                continue

            recovery.begin_validation_wait()
            ok = await asyncio.to_thread(recovery.wait_for_validation, validate_timeout)
            recovery.end_validation_wait()
            if ok:
                entry = recovery.finish_success()
                duration = 0.0
                if entry is not None:
                    try:
                        start_dt = datetime.fromisoformat(entry.started_at.replace("Z", "+00:00"))
                        end_dt = datetime.fromisoformat(entry.finished_at.replace("Z", "+00:00"))
                        duration = max(0.0, (end_dt - start_dt).total_seconds())
                    except ValueError:
                        duration = 0.0
                await notify_dave_alert(
                    self.config,
                    event="dave_decrypt_recovered",
                    channel_name=recovery.channel_name,
                    channel_id=recovery.channel_id,
                    gap_started_at=gap_started,
                    gap_duration_s=duration,
                    reconnect_attempts=attempt,
                )
                logger.info("[dave_recovery] Recuperação OK na tentativa %s", attempt)
                return

            logger.warning(
                "[dave_recovery] Tentativa %s: sem PCM OK em %.0fs",
                attempt,
                validate_timeout,
            )

        entry = recovery.finish_failed()
        attempts = entry.reconnect_attempts if entry else max_attempts
        await notify_dave_alert(
            self.config,
            event="dave_decrypt_failed",
            channel_name=recovery.channel_name,
            channel_id=recovery.channel_id,
            gap_started_at=gap_started,
            reconnect_attempts=attempts,
        )

        vc = self.voice_client
        if vc is not None and vc.is_connected():
            try:
                if vc.is_recording():
                    vc.stop_recording()
                await vc.disconnect(force=True)
            except Exception as exc:
                logger.warning("[dave_recovery] Falha ao sair do voz após esgotar: %s", exc)
        self.voice_client = None
        self.sink = None
        logger.error(
            "[dave_recovery] Tentativas esgotadas — sessão %s permanece aberta sem voz",
            recovery.session_id,
        )

    def _make_recording_finished_callback(self):
        def recording_finished(exception: Exception | None) -> None:
            if exception is None:
                return

            # Soft-restart for Opus/corrupt stream only — NOT DAVE key recovery.
            recoverable = "corrupted stream" in str(exception) or type(exception).__name__ == "OpusError"
            if recoverable:
                logger.warning("[session] Recording error (recuperável Opus): %s", exception)
            else:
                logger.error("[session] Recording error: %s", exception)
                return

            if self.dave_recovery.recovery_in_progress:
                return
            if self.session is None or self.voice_client is None or self.sink is None:
                return
            if not self.voice_client.is_connected() or self.voice_client.is_recording():
                return

            try:
                self.voice_client.start_recording(self.sink, recording_finished)
                logger.info("[session] Gravação reiniciada após erro Opus")
            except Exception as exc:
                logger.error("[session] Falha ao reiniciar gravação: %s", exc)

        return recording_finished

    async def _wait_dave_warmup(
        self,
        voice_client: discord.VoiceClient,
        *,
        ready_timeout: float = 15.0,
        settle_delay: float = 2.0,
    ) -> None:
        """Wait for DAVE MLS ready, then allow early decrypt failures to settle."""
        conn = voice_client._connection
        deadline = time.monotonic() + ready_timeout
        while time.monotonic() < deadline:
            dave = getattr(conn, "dave_session", None)
            if dave is not None and getattr(dave, "ready", False):
                break
            await asyncio.sleep(0.1)
        else:
            logger.warning(
                "[session] DAVE não ficou ready em %.0fs; iniciando gravação mesmo assim",
                ready_timeout,
            )

        if settle_delay > 0:
            await asyncio.sleep(settle_delay)

    def _reset(self) -> None:
        self.dave_recovery.detach()
        self.session = None
        self.session_dir = None
        self.speaking_log = None
        self.gaps_log = None
        self.voice_client = None
        self.sink = None
        self.started_monotonic = 0.0
        self._loop = None
        self._voice_channel = None
        self._bot_user_id = ""
        self._guild = None

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
