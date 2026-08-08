"""Contract tests for POST /transcribe-session."""

from __future__ import annotations

import json
from unittest.mock import patch

from whisper_service.session_store import reset_store_for_tests
from whisper_service.session_worker import process_session


def _session_payload(session_dir, callback_url="http://127.0.0.1:9/hook"):
    return {
        "session_id": session_dir.name,
        "recordings_path": str(session_dir),
        "speaking_log_path": str(session_dir / "speaking_log.jsonl"),
        "participants": [{"user_id": "111", "display_name": "Alice"}],
        "channel_id": "ch-1",
        "callback_url": callback_url,
    }


def _prepare_session(recordings_prefix, n=2):
    session = recordings_prefix / "sess-ok"
    session.mkdir()
    user_dir = session / "111"
    user_dir.mkdir()
    lines = []
    for i in range(1, n + 1):
        ogg = user_dir / f"{i:04d}.ogg"
        ogg.write_bytes(b"OggSfake")
        lines.append(
            json.dumps(
                {
                    "user_id": "111",
                    "seq": i,
                    "file": f"111/{i:04d}.ogg",
                    "start_ms": i * 1000,
                    "end_ms": i * 1000 + 500,
                    "duration_ms": 500,
                }
            )
        )
    (session / "speaking_log.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return session


def test_transcribe_session_accepted(ready_client, recordings_prefix):
    reset_store_for_tests()
    session = _prepare_session(recordings_prefix)

    def _inline(job, store=None):
        process_session(job, store)

    with (
        patch("whisper_service.session_worker.submit_session", side_effect=_inline),
        patch("whisper_service.transcriber.transcribe", return_value=("olá", 1.0)),
        patch("whisper_service.callback.notify", return_value=True) as notify,
    ):
        resp = ready_client.post("/transcribe-session", json=_session_payload(session))

    assert resp.status_code == 202
    assert resp.json() == {"status": "accepted", "session_id": "sess-ok"}
    assert (session / "transcricao.txt").is_file()
    text = (session / "transcricao.txt").read_text(encoding="utf-8")
    assert "[00:00:01] Alice: olá" in text
    notify.assert_called()
    status = ready_client.get("/status/sess-ok")
    assert status.status_code == 200
    assert status.json()["status"] == "done"


def test_transcribe_session_conflict_409(ready_client, recordings_prefix):
    reset_store_for_tests()
    session = _prepare_session(recordings_prefix)
    from whisper_service.session_store import get_store

    get_store().try_start("sess-ok", channel_id="c", callback_url="http://x")

    resp = ready_client.post("/transcribe-session", json=_session_payload(session))
    assert resp.status_code == 409
    assert "já está sendo processada" in resp.json()["detail"]


def test_transcribe_session_forbidden_path(ready_client, recordings_prefix, tmp_path):
    reset_store_for_tests()
    outside = tmp_path / "outside" / "sess"
    outside.mkdir(parents=True)
    (outside / "speaking_log.jsonl").write_text("", encoding="utf-8")
    payload = _session_payload(outside)
    payload["session_id"] = "bad"
    resp = ready_client.post("/transcribe-session", json=payload)
    assert resp.status_code == 403
