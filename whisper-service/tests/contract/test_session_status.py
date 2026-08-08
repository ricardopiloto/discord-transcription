"""Contract tests for GET /status/{session_id}."""

from __future__ import annotations

from whisper_service.session_store import get_store, reset_store_for_tests


def test_status_unknown_404(ready_client, recordings_prefix):
    reset_store_for_tests()
    resp = ready_client.get("/status/never-seen")
    assert resp.status_code == 404


def test_status_in_progress_and_done(ready_client, recordings_prefix):
    reset_store_for_tests()
    store = get_store()
    store.try_start("s1", channel_id="c", callback_url="http://x")
    store.set_total("s1", 10)
    store.set_processed("s1", 3)

    mid = ready_client.get("/status/s1")
    assert mid.status_code == 200
    body = mid.json()
    assert body["status"] == "in_progress"
    assert body["processed"] == 3
    assert body["total"] == 10

    store.mark_done(
        "s1",
        processed=10,
        total=10,
        utterances_com_texto=8,
        output_path="/tmp/t.txt",
    )
    done = ready_client.get("/status/s1")
    assert done.json()["status"] == "done"
    assert done.json()["output_path"] == "/tmp/t.txt"


def test_status_failed(ready_client, recordings_prefix):
    reset_store_for_tests()
    store = get_store()
    store.try_start("s2", channel_id="c", callback_url="http://x")
    store.mark_failed("s2", error="boom", processed=2, total=5)
    resp = ready_client.get("/status/s2")
    assert resp.status_code == 200
    assert resp.json()["status"] == "failed"
    assert resp.json()["error"] == "boom"
