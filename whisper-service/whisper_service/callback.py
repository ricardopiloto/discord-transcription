"""HTTP callback to n8n with bounded retries and backoff."""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any, Callable

logger = logging.getLogger(__name__)

DEFAULT_BACKOFFS_S = (2.0, 5.0, 10.0)
DEFAULT_TIMEOUT_S = 10.0


def notify(
    callback_url: str,
    payload: dict[str, Any],
    *,
    max_attempts: int = 3,
    backoffs_s: tuple[float, ...] = DEFAULT_BACKOFFS_S,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    sleep_fn: Callable[[float], None] = time.sleep,
    urlopen: Callable[..., Any] = urllib.request.urlopen,
) -> bool:
    """
    POST JSON to ``callback_url``.

    Returns True on first HTTP 2xx; False after exhausting attempts.
    """
    body = json.dumps(payload).encode("utf-8")
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        request = urllib.request.Request(
            callback_url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout_s) as response:
                status = getattr(response, "status", None) or response.getcode()
                if 200 <= int(status) < 300:
                    logger.info(
                        "Callback OK attempt=%s url=%s status=%s",
                        attempt,
                        callback_url,
                        status,
                    )
                    return True
                last_error = RuntimeError(f"HTTP {status}")
                logger.warning(
                    "Callback non-2xx attempt=%s/%s url=%s status=%s",
                    attempt,
                    max_attempts,
                    callback_url,
                    status,
                )
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            logger.warning(
                "Callback failed attempt=%s/%s url=%s error=%s",
                attempt,
                max_attempts,
                callback_url,
                exc,
            )

        if attempt < max_attempts:
            delay = backoffs_s[min(attempt - 1, len(backoffs_s) - 1)]
            sleep_fn(delay)

    logger.error(
        "Callback exhausted attempts=%s url=%s last_error=%s",
        max_attempts,
        callback_url,
        last_error,
    )
    return False
