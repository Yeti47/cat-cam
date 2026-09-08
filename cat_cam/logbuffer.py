from __future__ import annotations

import logging
from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .state import SharedState


class RingBufferHandler(logging.Handler):
    """Keeps recent log lines in memory and forwards new ones to the web
    UI's log subscribers, independent of systemd/journalctl -- so log
    viewing works the same whether the process is run as the service or
    manually."""

    def __init__(self, state: "SharedState", capacity: int = 1000):
        super().__init__()
        self._state = state
        self._buffer: deque[str] = deque(maxlen=capacity)

    def recent(self) -> list[str]:
        return list(self._buffer)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = self.format(record)
        except Exception:
            self.handleError(record)
            return
        self._buffer.append(line)
        self._state.publish_log(line)
