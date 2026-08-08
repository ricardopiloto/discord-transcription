"""Unit tests for in-memory session store."""

from __future__ import annotations

from whisper_service.session_store import SessionStore


def test_try_start_rejects_in_progress():
    store = SessionStore()
    assert store.try_start("s1", channel_id="c", callback_url="http://x") is True
    assert store.try_start("s1", channel_id="c", callback_url="http://x") is False


def test_reprocess_after_done():
    store = SessionStore()
    store.try_start("s1", channel_id="c", callback_url="http://x")
    store.mark_done(
        "s1",
        processed=2,
        total=2,
        utterances_com_texto=1,
        output_path="/tmp/t.txt",
    )
    assert store.try_start("s1", channel_id="c", callback_url="http://x") is True
    assert store.get("s1").status == "in_progress"


def test_mark_failed_clears_output():
    store = SessionStore()
    store.try_start("s1", channel_id="c", callback_url="http://x")
    store.mark_failed("s1", error="boom", processed=3, total=10)
    state = store.get("s1")
    assert state.status == "failed"
    assert state.error == "boom"
    assert state.output_path is None
    body = state.to_status_dict()
    assert body["error"] == "boom"
