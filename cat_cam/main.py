from __future__ import annotations

import argparse
import logging
import signal
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import cv2
import uvicorn

from .capture import Camera
from .config import Config
from .detector import CatDetector, Detection
from .log_buffer import RingBufferHandler
from .notifier import Notifier
from .state import SharedState

log = logging.getLogger("cat_cam")

# Continuous frame-grab rate for the live web feed, decoupled from
# detection.interval_seconds (which still gates how often YOLO runs).
_STREAM_FPS = 10.0


def _draw_boxes(frame, detections: list[Detection]):
    annotated = frame.copy()
    for det in detections:
        x1, y1, x2, y2 = det.box
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
        label = f"cat {det.confidence:.2f}"
        cv2.putText(annotated, label, (x1, max(0, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    return annotated


def _cleanup_old_snapshots(snapshot_dir: Path, retention_days: int) -> None:
    cutoff = datetime.now() - timedelta(days=retention_days)
    for path in snapshot_dir.glob("cat_*.jpg"):
        try:
            if datetime.fromtimestamp(path.stat().st_mtime) < cutoff:
                path.unlink()
        except OSError as exc:
            log.warning("Could not clean up snapshot %s: %s", path, exc)


class CatCamApp:
    def __init__(self, config: Config, state: SharedState):
        self.config = config
        self.state = state
        self.camera = Camera(config.camera)
        self.detector = CatDetector(config.detection)
        self.notifier = Notifier(config.notify)
        self.snapshot_dir = Path(config.snapshot.dir)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

        self._running = True
        self._consecutive_hits = 0
        self._last_seen_time = 0.0
        self._cat_present = False

    def stop(self, *_args) -> None:
        log.info("Shutting down")
        self._running = False

    def _save_snapshot(self, frame, detections: list[Detection]) -> Optional[Path]:
        if not self.config.snapshot.enabled:
            return None
        annotated = _draw_boxes(frame, detections)
        filename = f"cat_{datetime.now():%Y%m%d_%H%M%S}.jpg"
        path = self.snapshot_dir / filename
        cv2.imwrite(str(path), annotated)
        _cleanup_old_snapshots(self.snapshot_dir, self.config.snapshot.retention_days)
        return path

    def _handle_detection(self, frame, detections: list[Detection], now: float) -> None:
        cfg = self.config.detection

        if detections:
            self._consecutive_hits += 1
            self._last_seen_time = now
        else:
            self._consecutive_hits = 0

        if not self._cat_present and self._consecutive_hits >= cfg.consecutive_frames_required:
            self._cat_present = True
            best = max(detections, key=lambda d: d.confidence)
            snapshot_path = self._save_snapshot(frame, detections)
            night_note = " (dark, night mode)" if best.is_night else ""
            self.notifier.notify(
                title="Cat at the door 🐱",
                message=f"Cat detected outside{night_note} (confidence {best.confidence:.0%})",
                snapshot_path=snapshot_path,
            )
            self.state.publish_detection(
                {"type": "detection", "confidence": best.confidence, "is_night": best.is_night}
            )
            log.info("Notified: cat detected (confidence %.2f)", best.confidence)
        elif self._cat_present and (now - self._last_seen_time) >= cfg.absence_reset_seconds:
            self._cat_present = False
            log.info("Cat no longer visible, re-armed for next notification")

    def run(self) -> None:
        log.info("cat-cam started, watching %s", self.config.camera.device)
        capture_interval = 1.0 / _STREAM_FPS
        last_detect = 0.0

        while self._running:
            loop_start = time.monotonic()

            frame = self.camera.read()
            if frame is None:
                time.sleep(1.0)
                continue

            now = time.monotonic()
            zone = self.config.detection.zone
            detections: list[Detection] = []
            if (now - last_detect) >= self.config.detection.interval_seconds:
                detections = self.detector.detect(frame, zone)
                last_detect = now
                self._handle_detection(frame, detections, now)

            self.state.set_frame(frame, detections)

            elapsed = time.monotonic() - loop_start
            time.sleep(max(0.0, capture_interval - elapsed))

        self.camera.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Notify when a cat is at the door")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    args = parser.parse_args()

    config = Config.load(args.config)
    log_format = "%(asctime)s %(levelname)s %(name)s: %(message)s"
    logging.basicConfig(
        level=getattr(logging, config.logging_level.upper(), logging.INFO),
        format=log_format,
    )

    state = SharedState()
    ring_handler = RingBufferHandler(state)
    ring_handler.setFormatter(logging.Formatter(log_format))
    logging.getLogger("cat_cam").addHandler(ring_handler)

    app = CatCamApp(config, state)
    thread = threading.Thread(target=app.run, name="capture", daemon=True)
    thread.start()

    if config.web.enabled:
        from .web import create_app

        log.info("Web UI listening on http://%s:%d", config.web.host, config.web.port)
        uvicorn.run(
            create_app(app, ring_handler),
            host=config.web.host,
            port=config.web.port,
            log_level="warning",
            # A client that vanishes mid-stream (MJPEG feed, SSE tail) can
            # otherwise leave a background task uvicorn waits on forever;
            # bound it so SIGTERM (systemd stop/restart) always completes.
            timeout_graceful_shutdown=5,
        )
        app.stop()
        thread.join(timeout=5)
    else:
        signal.signal(signal.SIGINT, app.stop)
        signal.signal(signal.SIGTERM, app.stop)
        thread.join()


if __name__ == "__main__":
    main()
