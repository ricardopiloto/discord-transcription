"""Incremental utterance sink — writes to disk per segment, not whole session."""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
import threading
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable

import discord
from discord.sinks import Sink

from cronista.recording.speaking_log import SpeakingLog
from cronista.recording.storage import format_utterance_filename, write_session_json
from cronista.session import SpeakingLogEntry

logger = logging.getLogger(__name__)

SAMPLE_RATE = 48_000
CHANNELS = 2
SAMPLE_WIDTH = 2

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

    def __init__(
        self,
        *,
        session_dir: Path,
        session_started_monotonic: float,
        speaking_log: SpeakingLog,
        utterance_silence_ms: int,
        bot_user_id: str,
        guild: discord.Guild,
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
        self.loop = loop
        self.on_participant = on_participant
        self.on_utterance_complete = on_utterance_complete

        self.seq_counters: dict[str, int] = {}
        self.open_utterances: dict[str, OpenUtterance] = {}
        self.timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

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

    async def _resolve_member(self, user_id: str) -> discord.Member | None:
        member = self.guild.get_member(int(user_id))
        if member is None:
            try:
                member = await self.guild.fetch_member(int(user_id))
            except discord.HTTPException:
                return None
        if member.user.bot:
            return None
        return member

    async def _start_utterance(self, user_id: str) -> None:
        if user_id in self.open_utterances:
            return

        member = await self._resolve_member(user_id)
        if member is None:
            return

        display_name = member.display_name or member.name
        await self.on_participant(user_id, display_name)

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

    def write(self, data: bytes, user: int) -> None:
        user_id = str(user)
        if user_id == self.bot_user_id:
            return

        member = self.guild.get_member(user)
        if member is not None and member.bot:
            return

        with self._lock:
            if user_id not in self.open_utterances:
                asyncio.run_coroutine_threadsafe(self._start_utterance(user_id), self.loop).result()

            open_ut = self.open_utterances.get(user_id)
            if open_ut is not None:
                open_ut.wav.writeframes(data)

            self._schedule_close(user_id)

    async def _close_utterance(self, user_id: str) -> None:
        self._cancel_timer(user_id)
        open_ut = self.open_utterances.pop(user_id, None)
        if open_ut is None:
            return

        open_ut.wav.close()
        ogg_path = open_ut.wav_path.with_suffix(".ogg")
        converted = _convert_wav_to_ogg(open_ut.wav_path, ogg_path)
        if converted:
            open_ut.wav_path.unlink(missing_ok=True)
            final_path = ogg_path
        else:
            final_path = open_ut.wav_path

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
