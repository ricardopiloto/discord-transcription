"""IncrementalUtteranceSink compatibility with py-cord 2.8 voice receive."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from discord.voice.receive.router import SinkEventRouter

from cronista.recording.sink import IncrementalUtteranceSink
from cronista.recording.speaking_log import SpeakingLog


@pytest.fixture
def sink(tmp_path: Path) -> IncrementalUtteranceSink:
    session_dir = tmp_path / "20260711-120000"
    session_dir.mkdir()
    speaking_log = SpeakingLog(session_dir)
    guild = MagicMock()
    guild.get_member.return_value = None
    guild.fetch_member = MagicMock()

    return IncrementalUtteranceSink(
        session_dir=session_dir,
        session_started_monotonic=0.0,
        speaking_log=speaking_log,
        utterance_silence_ms=1000,
        bot_user_id="999",
        guild=guild,
        loop=asyncio.get_event_loop(),
        on_participant=MagicMock(),
        on_utterance_complete=MagicMock(),
    )


def test_sink_exposes_pycord_voice_receive_hooks(sink: IncrementalUtteranceSink) -> None:
    assert hasattr(sink, "__sink_listeners__")
    assert list(sink.walk_children()) == []

    reader = MagicMock()
    reader.packet_router._lock = __import__("threading").RLock()
    SinkEventRouter(sink, reader)
