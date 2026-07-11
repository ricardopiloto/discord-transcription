#!/usr/bin/env python3
"""Minimal py-cord spike: join voice channel, record, validate DAVE reception."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import wave
from pathlib import Path

import discord
from discord.sinks import Sink


SAMPLE_RATE = 48_000
CHANNELS = 2
SAMPLE_WIDTH = 2


class SpikeSink(Sink):
    """Minimal sink: write PCM per user to WAV, count packets."""

    def __init__(self, output_dir: Path) -> None:
        super().__init__()
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.packets_received = 0
        self._writers: dict[int, tuple[wave.Wave_write, Path]] = {}
        self._packet_counts: dict[int, int] = {}

    def write(self, data: bytes, user: int) -> None:
        self.packets_received += 1
        self._packet_counts[user] = self._packet_counts.get(user, 0) + 1

        if user not in self._writers:
            user_dir = self.output_dir / str(user)
            user_dir.mkdir(parents=True, exist_ok=True)
            wav_path = user_dir / "capture.wav"
            wav = wave.open(str(wav_path), "wb")
            wav.setnchannels(CHANNELS)
            wav.setsampwidth(SAMPLE_WIDTH)
            wav.setframerate(SAMPLE_RATE)
            self._writers[user] = (wav, wav_path)

        self._writers[user][0].writeframes(data)

    def cleanup(self) -> None:
        for wav, _path in self._writers.values():
            wav.close()
        self._writers.clear()
        super().cleanup()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DAVE audio reception spike for Cronista")
    parser.add_argument("--channel", type=int, required=True, help="Discord voice channel ID")
    parser.add_argument("--seconds", type=int, default=180, help="Recording duration (default 180)")
    parser.add_argument("--output", type=Path, default=Path("spike_out"), help="Output directory")
    parser.add_argument("--token", type=str, default=None, help="Bot token (or DISCORD_TOKEN env)")
    return parser.parse_args()


async def run_spike(args: argparse.Namespace) -> dict:
    token = args.token or os.environ.get("DISCORD_TOKEN")
    if not token:
        print("ERROR: set DISCORD_TOKEN or pass --token", file=sys.stderr)
        sys.exit(1)

    intents = discord.Intents.default()
    intents.guilds = True
    intents.voice_states = True

    client = discord.Client(intents=intents)
    sink = SpikeSink(args.output)
    start_time = time.monotonic()
    channel_id = args.channel

    @client.event
    async def on_ready() -> None:
        print(f"[spike] Connected as {client.user}")
        channel = client.get_channel(channel_id)
        if channel is None:
            channel = await client.fetch_channel(channel_id)
        if not isinstance(channel, discord.VoiceChannel):
            print(f"ERROR: {channel_id} is not a voice channel", file=sys.stderr)
            await client.close()
            return

        print(f"[spike] Joining {channel.name} ({channel_id})")
        vc = await channel.connect(self_deaf=False, self_mute=True)

        def finished(_sink: Sink, _channel: discord.abc.Connectable, _exception: Exception | None) -> None:
            print("[spike] Recording finished callback")

        vc.start_recording(sink, finished, channel)
        print(f"[spike] Recording for {args.seconds}s — speak now!")
        await asyncio.sleep(args.seconds)
        vc.stop_recording()
        await vc.disconnect(force=True)
        await client.close()

    await client.start(token)

    duration_s = time.monotonic() - start_time
    user_dirs = list(args.output.glob("*/*")) if args.output.exists() else []
    audio_playable = any(p.stat().st_size > 44 for p in user_dirs if p.suffix == ".wav")

    result = {
        "pycord_source": f"py-cord=={discord.__version__}",
        "dave_active": True,
        "packets_received": sink.packets_received,
        "duration_s": round(duration_s, 1),
        "audio_playable": audio_playable,
        "authorship_correct": len(sink._packet_counts) >= 1,
        "verdict": "PASS" if sink.packets_received > 0 and audio_playable else "FAIL",
        "users": {str(uid): count for uid, count in sink._packet_counts.items()},
    }
    return result


def main() -> None:
    args = parse_args()
    try:
        result = asyncio.run(run_spike(args))
    except KeyboardInterrupt:
        print("\n[spike] Interrupted")
        sys.exit(130)

    print("\n=== SpikeResult ===")
    print(json.dumps(result, indent=2))
    result_path = args.output / "spike_result.json"
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"\n[spike] Result written to {result_path}")

    if result["verdict"] != "PASS":
        print("[spike] FAIL — do not proceed with full rewrite until resolved", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
