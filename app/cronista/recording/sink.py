"""Incremental utterance sink — writes to disk per segment, not whole session."""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
import threading
import time
import wave
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, ClassVar

import discord
from discord.sinks import Sink

from cronista.recording.speaking_log import SpeakingLog
from cronista.recording.storage import format_utterance_filename
from cronista.session import SpeakingLogEntry

logger = logging.getLogger(__name__)

SAMPLE_RATE = 48_000
CHANNELS = 2
SAMPLE_WIDTH = 2
PCM_SILENCE_THRESHOLD = 512


def is_silent_pcm(pcm: bytes, threshold: int = PCM_SILENCE_THRESHOLD) -> bool:
    """True when every sample is below *threshold* (DAVE warm-up / Opus silence frames)."""
    if len(pcm) < 2:
        return True
    peak = 0
    for i in range(0, len(pcm) - 1, 2):
        sample = int.from_bytes(pcm[i : i + 2], "little", signed=True)
        if sample < 0:
            sample = -sample
        if sample > peak:
            peak = sample
            if peak >= threshold:
                return False
    return True


def wav_has_audio(wav_path: Path, threshold: int = PCM_SILENCE_THRESHOLD) -> bool:
    if wav_path.stat().st_size <= 44:
        return False
    with wave.open(str(wav_path), "rb") as wf:
        pcm = wf.readframes(wf.getnframes())
    return not is_silent_pcm(pcm, threshold)


OnParticipant = Callable[[str, str], Awaitable[None]]
OnUtteranceComplete = Callable[[str], Awaitable[None]]


@dataclass
class OpenUtterance:
    user_id: str
    seq: int
    start_ms: int
    wav_path: Path
    wav: wave.Wave_write


class IncrementalUtteranceSink(Sink):
    """Custom sink: PCM chunks written incrementally; utterance closed on silence."""

    # py-cord 2.8 voice receive router expects these on every sink subclass.
    __sink_listeners__: ClassVar[list[tuple[str, str]]] = []

    def is_opus(self) -> bool:
        """Tell py-cord to decode Opus → PCM before calling write()."""
        return False

    def __init__(
        self,
        *,
        session_dir: Path,
        session_started_monotonic: float,
        speaking_log: SpeakingLog,
        utterance_silence_ms: int,
        bot_user_id: str,
        guild: discord.Guild,
        voice_channel: discord.VoiceChannel,
        loop: asyncio.AbstractEventLoop,
        on_participant: OnParticipant,
        on_utterance_complete: OnUtteranceComplete,
    ) -> None:
        super().__init__()
        self.session_dir = session_dir
        self.session_started_monotonic = session_started_monotonic
        self.speaking_log = speaking_log
        self.utterance_silence_ms = utterance_silence_ms
        self.bot_user_id = bot_user_id
        self.guild = guild
        self.voice_channel = voice_channel
        self.loop = loop
        self.on_participant = on_participant
        self.on_utterance_complete = on_utterance_complete

        self.seq_counters: dict[str, int] = {}
        self.open_utterances: dict[str, OpenUtterance] = {}
        self.timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()
        self.packets_received = 0
        self.pcm_bytes_received = 0

    def walk_children(self, *, with_self: bool = False) -> Iterator[IncrementalUtteranceSink]:
        if with_self:
            yield self

    def cleanup(self) -> None:
        self.finished = True

    def _elapsed_ms(self) -> int:
        return int((time.monotonic() - self.session_started_monotonic) * 1000)

    def _cancel_timer(self, user_id: str) -> None:
        timer = self.timers.pop(user_id, None)
        if timer is not None:
            timer.cancel()

    def _schedule_close(self, user_id: str) -> None:
        self._cancel_timer(user_id)

        def _fire(uid: str = user_id) -> None:
            asyncio.run_coroutine_threadsafe(self._close_utterance(uid), self.loop)

        timer = threading.Timer(self.utterance_silence_ms / 1000.0, _fire)
        timer.daemon = True
        self.timers[user_id] = timer
        timer.start()

    def _find_member(self, user_id: int) -> discord.Member | None:
        for member in self.voice_channel.members:
            if member.id == user_id:
                return member
        return self.guild.get_member(user_id)

    def _display_name_sync(self, user_id: str) -> str:
        member = self._find_member(int(user_id))
        if member is not None and not member.bot:
            return member.display_name or member.name
        return f"user-{user_id}"

    async def _resolve_display_name(self, user_id: str) -> str:
        uid = int(user_id)
        member = self._find_member(uid)
        if member is not None and not member.bot:
            return member.display_name or member.name

        try:
            member = await self.guild.fetch_member(uid)
            if not member.bot:
                return member.display_name or member.name
        except discord.HTTPException:
            pass

        try:
            user = await self.guild.fetch_user(uid)
            return user.display_name or user.name
        except discord.HTTPException:
            logger.warning("[recorder] Não foi possível resolver nome do usuário %s", user_id)
            return f"user-{user_id}"

    def _extract_user_id(self, data, user) -> int | None:
        if user is not None:
            raw_user_id = getattr(user, "id", user)
            if raw_user_id is not None:
                return int(raw_user_id)

        packet = getattr(data, "packet", None)
        voice_client = self.vc
        if packet is not None and voice_client is not None:
            ssrc = getattr(packet, "ssrc", None)
            if ssrc is not None:
                mapped = voice_client._ssrc_to_id.get(ssrc)
                if mapped is not None:
                    return int(mapped)
        return None

    def _is_bot_user(self, user_id: int) -> bool:
        if str(user_id) == self.bot_user_id:
            return True
        member = self._find_member(user_id)
        return member is not None and member.bot

    def _open_utterance_sync(self, user_id: str) -> None:
        if user_id in self.open_utterances:
            return

        seq = self.seq_counters.get(user_id, 0) + 1
        self.seq_counters[user_id] = seq

        user_dir = self.session_dir / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        wav_path = user_dir / f"{seq:04d}.wav"

        wav = wave.open(str(wav_path), "wb")
        wav.setnchannels(CHANNELS)
        wav.setsampwidth(SAMPLE_WIDTH)
        wav.setframerate(SAMPLE_RATE)

        self.open_utterances[user_id] = OpenUtterance(
            user_id=user_id,
            seq=seq,
            start_ms=self._elapsed_ms(),
            wav_path=wav_path,
            wav=wav,
        )
        logger.info("[recorder] Utterance aberta %s/%04d.wav", user_id, seq)

    def _schedule_participant_register(self, user_id: str) -> None:
        display_name = self._display_name_sync(user_id)

        async def _register() -> None:
            await self.on_participant(user_id, display_name)
            resolved = await self._resolve_display_name(user_id)
            if resolved != display_name:
                await self.on_participant(user_id, resolved)

        asyncio.run_coroutine_threadsafe(_register(), self.loop)

    def write(self, data, user) -> None:
        pcm = getattr(data, "pcm", data)
        if not pcm:
            return

        if is_silent_pcm(pcm):
            return

        self.packets_received += 1
        self.pcm_bytes_received += len(pcm)
        if self.packets_received == 1:
            logger.info("[recorder] Primeiro pacote de áudio recebido (%s bytes PCM)", len(pcm))
        elif self.packets_received % 500 == 0:
            logger.info(
                "[recorder] %s pacotes recebidos (%s bytes PCM acumulados)",
                self.packets_received,
                self.pcm_bytes_received,
            )

        raw_user_id = self._extract_user_id(data, user)
        if raw_user_id is None:
            if self.packets_received <= 5:
                logger.warning("[recorder] Pacote de áudio sem user_id mapeado (ssrc/user ausente)")
            return

        if self._is_bot_user(raw_user_id):
            return

        user_id = str(raw_user_id)

        with self._lock:
            if user_id not in self.open_utterances:
                self._open_utterance_sync(user_id)
                self._schedule_participant_register(user_id)

            open_ut = self.open_utterances.get(user_id)
            if open_ut is not None:
                open_ut.wav.writeframes(pcm)

            self._schedule_close(user_id)

    async def _close_utterance(self, user_id: str) -> None:
        with self._lock:
            self._cancel_timer(user_id)
            open_ut = self.open_utterances.pop(user_id, None)

        if open_ut is None:
            return

        open_ut.wav.close()

        if not wav_has_audio(open_ut.wav_path):
            open_ut.wav_path.unlink(missing_ok=True)
            logger.info(
                "[recorder] Utterance descartada (apenas silêncio) %s/%04d",
                user_id,
                open_ut.seq,
            )
            return

        ogg_path = open_ut.wav_path.with_suffix(".ogg")
        converted = _convert_wav_to_ogg(open_ut.wav_path, ogg_path)
        if converted:
            open_ut.wav_path.unlink(missing_ok=True)
        else:
            ogg_path = open_ut.wav_path

        end_ms = self._elapsed_ms()
        rel_file = f"{user_id}/{format_utterance_filename(open_ut.seq)}"
        if not converted:
            rel_file = f"{user_id}/{open_ut.seq:04d}.wav"

        entry = SpeakingLogEntry(
            user_id=user_id,
            seq=open_ut.seq,
            file=rel_file,
            start_ms=open_ut.start_ms,
            end_ms=end_ms,
            duration_ms=end_ms - open_ut.start_ms,
        )
        await self.speaking_log.append(entry)
        await self.on_utterance_complete(user_id)
        logger.info(
            "[recorder] Utterance %s/%s (%sms)",
            user_id,
            rel_file.split("/")[-1],
            entry.duration_ms,
        )

    async def flush_all(self) -> None:
        for user_id in list(self.open_utterances):
            await self._close_utterance(user_id)


def _convert_wav_to_ogg(wav_path: Path, ogg_path: Path) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        logger.warning("[recorder] ffmpeg not found; keeping WAV for %s", wav_path.name)
        return False
    try:
        subprocess.run(
            [ffmpeg, "-y", "-i", str(wav_path), "-c:a", "libopus", str(ogg_path)],
            check=True,
            capture_output=True,
        )
        return True
    except subprocess.CalledProcessError as exc:
        logger.error("[recorder] ffmpeg conversion failed: %s", exc.stderr.decode(errors="replace"))
        return False
