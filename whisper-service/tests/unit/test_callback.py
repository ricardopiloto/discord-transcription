"""Unit tests for callback retries."""

from __future__ import annotations

from unittest.mock import MagicMock

from whisper_service.callback import notify


class _Resp:
    def __init__(self, status: int):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def getcode(self):
        return self.status

    def read(self):
        return b"ok"


def test_notify_succeeds_first_try():
    sleeps: list[float] = []
    urlopen = MagicMock(return_value=_Resp(200))
    ok = notify(
        "http://example.test/hook",
        {"status": "done"},
        sleep_fn=sleeps.append,
        urlopen=urlopen,
    )
    assert ok is True
    assert urlopen.call_count == 1
    assert sleeps == []


def test_notify_retries_then_succeeds():
    sleeps: list[float] = []
    urlopen = MagicMock(side_effect=[OSError("down"), OSError("down"), _Resp(200)])
    ok = notify(
        "http://example.test/hook",
        {"status": "done"},
        sleep_fn=sleeps.append,
        urlopen=urlopen,
        backoffs_s=(0.01, 0.02, 0.03),
    )
    assert ok is True
    assert urlopen.call_count == 3
    assert sleeps == [0.01, 0.02]


def test_notify_exhausts_attempts():
    sleeps: list[float] = []
    urlopen = MagicMock(side_effect=OSError("down"))
    ok = notify(
        "http://example.test/hook",
        {"status": "failed", "error": "x"},
        sleep_fn=sleeps.append,
        urlopen=urlopen,
        backoffs_s=(0.01, 0.02, 0.03),
    )
    assert ok is False
    assert urlopen.call_count == 3
    assert len(sleeps) == 2
