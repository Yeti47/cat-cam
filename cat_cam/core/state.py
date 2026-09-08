from __future__ import annotations

import queue
import threading
from typing import Optional

import cv2
import numpy as np

class _Broadcaster:
    """Thread-safe fan-out to a set of per-subscriber queues. Used for both
    the detection-event feed and the log-tail feed."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: set[queue.Queue] = set()

    def subscribe(self) -> "queue.Queue":
        q: queue.Queue = queue.Queue(maxsize=100)
        with self._lock:
            self._subscribers.add(q)
        return q

    def unsubscribe(self, q: "queue.Queue") -> None:
        with self._lock:
            self._subscribers.discard(q)

    def publish(self, item) -> None:
        with self._lock:
            subscribers = list(self._subscribers)
        for q in subscribers:
            try:
                q.put_nowait(item)
            except queue.Full:
                pass  # slow client -- drop rather than block the publisher


class SharedState:
    """Thread-safe handoff point between the capture/detect background
    thread and the web server: the latest encoded frame, and pub/sub feeds
    for detection events and log lines."""

    def __init__(self) -> None:
        self._frame_lock = threading.Lock()
        self._jpeg: Optional[bytes] = None
        self._detections = _Broadcaster()
        self._logs = _Broadcaster()

    def set_frame(self, frame: np.ndarray, detections: list) -> None:
        # The zone rectangle is intentionally NOT drawn into the stream --
        # it's overlaid client-side instead, so each viewer can show/hide it
        # independently without re-encoding the shared frame.
        annotated = frame.copy()

        for det in detections:
            x1, y1, x2, y2 = det.box
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
            label = f"cat {det.confidence:.2f}"
            cv2.putText(annotated, label, (x1, max(0, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        ok, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ok:
            return
        with self._frame_lock:
            self._jpeg = buf.tobytes()

    def get_jpeg(self) -> Optional[bytes]:
        with self._frame_lock:
            return self._jpeg

    def publish_detection(self, event: dict) -> None:
        self._detections.publish(event)

    def subscribe_detections(self) -> "queue.Queue":
        return self._detections.subscribe()

    def unsubscribe_detections(self, q: "queue.Queue") -> None:
        self._detections.unsubscribe(q)

    def publish_log(self, line: str) -> None:
        self._logs.publish(line)

    def subscribe_logs(self) -> "queue.Queue":
        return self._logs.subscribe()

    def unsubscribe_logs(self, q: "queue.Queue") -> None:
        self._logs.unsubscribe(q)
