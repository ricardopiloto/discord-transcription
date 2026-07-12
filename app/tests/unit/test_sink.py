"""IncrementalUtteranceSink compatibility with py-cord 2.8 voice receive."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from discord.voice.receive.router import SinkEventRouter

from cronista.recording.sink import IncrementalUtteranceSink, is_silent_pcm
from cronista.recording.speaking_log import SpeakingLog


def _make_sink(tmp_path: Path, *, members: list[discord.Member] | None = None) -> IncrementalUtteranceSink:
    session_dir = tmp_path / "20260711-120000"
    session_dir.mkdir()
    speaking_log = SpeakingLog(session_dir)
    guild = MagicMock()
    guild.get_member.return_value = None
    guild.fetch_member = AsyncMock(side_effect=discord.HTTPException(MagicMock(), "not found"))
    guild.fetch_user = AsyncMock(side_effect=discord.HTTPException(MagicMock(), "not found"))

    voice_channel = MagicMock()
    voice_channel.members = members or []

    return IncrementalUtteranceSink(
        session_dir=session_dir,
        session_started_monotonic=0.0,
        speaking_log=speaking_log,
        utterance_silence_ms=1000,
        bot_user_id="999",
        guild=guild,
        voice_channel=voice_channel,
        loop=asyncio.new_event_loop(),
        on_participant=AsyncMock(),
        on_utterance_complete=AsyncMock(),
    )


@pytest.fixture
def sink(tmp_path: Path) -> IncrementalUtteranceSink:
    return _make_sink(tmp_path)


def test_sink_exposes_pycord_voice_receive_hooks(sink: IncrementalUtteranceSink) -> None:
    assert hasattr(sink, "__sink_listeners__")
    assert list(sink.walk_children()) == []
    assert sink.is_opus() is False

    reader = MagicMock()
    reader.packet_router._lock = __import__("threading").RLock()
    SinkEventRouter(sink, reader)


def test_extract_user_id_from_ssrc_when_source_missing(sink: IncrementalUtteranceSink) -> None:
    packet = MagicMock()
    packet.ssrc = 42
    data = MagicMock()
    data.packet = packet
    sink.vc = MagicMock()
    sink.vc._ssrc_to_id = {42: 123456789}

    assert sink._extract_user_id(data, None) == 123456789


@pytest.mark.asyncio
async def test_resolve_display_name_uses_voice_channel_member(tmp_path: Path) -> None:
    member = MagicMock()
    member.id = 111
    member.bot = False
    member.display_name = "Aragorn"
    member.name = "aragorn"

    sink = _make_sink(tmp_path, members=[member])
    assert await sink._resolve_display_name("111") == "Aragorn"


@pytest.mark.asyncio
async def test_resolve_display_name_falls_back_to_user_id(tmp_path: Path) -> None:
    sink = _make_sink(tmp_path)
    assert await sink._resolve_display_name("222") == "user-222"


def test_open_utterance_sync_creates_wav(sink: IncrementalUtteranceSink, tmp_path: Path) -> None:
    sink._open_utterance_sync("12345")
    wav_path = tmp_path / "20260711-120000" / "12345" / "0001.wav"
    assert wav_path.exists()
    assert "12345" in sink.open_utterances


def test_is_silent_pcm_detects_dave_warmup_frames() -> None:
    silence = b"\x00\x00" * 1920
    assert is_silent_pcm(silence) is True

    speech = silence[:100] + (1000).to_bytes(2, "little", signed=True) + silence[102:]
    assert is_silent_pcm(speech) is False


def test_write_skips_silent_pcm(sink: IncrementalUtteranceSink) -> None:
    silence = b"\x00\x00" * 1920
    sink.write(silence, None)
    assert sink.packets_received == 0
    assert sink.open_utterances == {}
