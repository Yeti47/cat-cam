from __future__ import annotations

import logging
import threading
import time
from typing import Optional

import cv2

from ..settings import Settings
from ..store import SettingsStore
from .camera import Camera
from .detector import CatDetector, Detection
from .notifier import Notifier
from .snapshots import SnapshotStore
from .state import SharedState

log = logging.getLogger(__name__)

# Continuous frame-grab rate for the live web feed, decoupled from
# settings.interval_seconds (which still gates how often YOLO runs).
_STREAM_FPS = 10.0


def draw_boxes(frame, detections: list[Detection]):
    annotated = frame.copy()
    for det in detections:
        x1, y1, x2, y2 = det.box
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
        label = f"cat {det.confidence:.2f}"
        cv2.putText(annotated, label, (x1, max(0, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    return annotated


class Pipeline:
    """Capture + detect loop, run on a background thread.

    Settings are re-read from the store every iteration, so changes made
    in the Web UI take effect without a restart.
    """

    def __init__(self, settings: Settings, store: SettingsStore, state: SharedState):
        self.settings = settings
        self.store = store
        self.state = state

        self.camera = Camera(settings.camera_device, settings.camera_crop)
        self.detector = CatDetector(settings.model_file, settings.class_name)
        self.notifier = Notifier(settings.ntfy_server, settings.ntfy_topic)
        self.snapshots = SnapshotStore(settings.snapshot_dir)

        self._thread: Optional[threading.Thread] = None
        # Interruptible sleeps: waiting on this instead of time.sleep means
        # stop() is noticed immediately rather than after the current sleep.
        self._stop_event = threading.Event()
        self._consecutive_hits = 0
        self._last_seen_time = 0.0
        self._cat_present = False

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="pipeline", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

    def _handle_detection(self, frame, detections: list[Detection], now: float) -> None:
        settings = self.store.get()

        if detections:
            self._consecutive_hits += 1
            self._last_seen_time = now
        else:
            self._consecutive_hits = 0

        if not self._cat_present and self._consecutive_hits >= settings.consecutive_frames_required:
            self._cat_present = True
            best = max(detections, key=lambda d: d.confidence)

            snapshot_path = None
            if settings.snapshots_enabled:
                snapshot_path = self.snapshots.save(
                    draw_boxes(frame, detections), best.confidence, best.is_night
                )
                self.snapshots.cleanup(settings.snapshot_retention_days)

            if settings.notifications_enabled and self.settings.ntfy_enabled:
                night_note = " (dark, night mode)" if best.is_night else ""
                self.notifier.notify(
                    title="Cat at the door 🐱",
                    message=f"Cat detected outside{night_note} (confidence {best.confidence:.0%})",
                    snapshot_path=snapshot_path,
                )

            self.state.publish_detection(
                {
                    "type": "detection",
                    "confidence": best.confidence,
                    "is_night": best.is_night,
                    "snapshot": snapshot_path.name if snapshot_path else None,
                }
            )
            log.info("Notified: cat detected (confidence %.2f)", best.confidence)
        elif self._cat_present and (now - self._last_seen_time) >= settings.absence_reset_seconds:
            self._cat_present = False
            log.info("Cat no longer visible, re-armed for next notification")

    def _run(self) -> None:
        log.info("cat-cam pipeline started, watching %s", self.settings.camera_device)
        capture_interval = 1.0 / _STREAM_FPS
        last_detect = 0.0

        while not self._stop_event.is_set():
            loop_start = time.monotonic()

            frame = self.camera.read()
            if frame is None:
                self._stop_event.wait(1.0)
                continue

            now = time.monotonic()
            settings = self.store.get()
            detections: list[Detection] = []
            if (now - last_detect) >= settings.interval_seconds:
                detections = self.detector.detect(frame, settings)
                last_detect = now
                self._handle_detection(frame, detections, now)

            self.state.set_frame(frame, detections)

            elapsed = time.monotonic() - loop_start
            self._stop_event.wait(max(0.0, capture_interval - elapsed))

        self.camera.close()
        log.info("cat-cam pipeline stopped")
