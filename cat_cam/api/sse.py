"""Shared Server-Sent Events plumbing.

These endpoints are sync generators, which Starlette iterates in a worker
thread. A thread blocked in `queue.get()` keeps running until that call
returns, and the process can't exit while it does -- so the blocking wait
must be short even though keep-alives are infrequent. Polling on a short
timeout and counting idle time separates the two: shutdown is noticed
within POLL_SECONDS, while keep-alives stay every KEEPALIVE_SECONDS.

Getting this wrong is not subtle: a long blocking wait means the
container misses its stop deadline and gets SIGKILLed.
"""

from __future__ import annotations

import json
import queue
import threading
from typing import Callable, Iterator

POLL_SECONDS = 1.0
KEEPALIVE_SECONDS = 15.0


def sse_stream(
    subscribe: Callable[[], queue.Queue],
    unsubscribe: Callable[[queue.Queue], None],
    shutdown: threading.Event,
) -> Iterator[str]:
    q = subscribe()
    try:
        idle = 0.0
        while not shutdown.is_set():
            try:
                item = q.get(timeout=POLL_SECONDS)
            except queue.Empty:
                idle += POLL_SECONDS
                if idle >= KEEPALIVE_SECONDS:
                    idle = 0.0
                    yield ": keep-alive\n\n"
                continue
            idle = 0.0
            yield f"data: {json.dumps(item)}\n\n"
    finally:
        unsubscribe(q)
