from __future__ import annotations

import logging
from typing import Optional

import cv2
import numpy as np

from .config import CameraConfig

log = logging.getLogger(__name__)


class Camera:
    """Thin wrapper around a v4l2 video device (e.g. the DroidCam
    virtual camera), with automatic reconnect if the stream drops."""

    def __init__(self, config: CameraConfig):
        self._config = config
        self._cap: Optional[cv2.VideoCapture] = None

    def _open(self) -> bool:
        cap = cv2.VideoCapture(self._config.device, cv2.CAP_V4L2)
        if not cap.isOpened():
            cap.release()
            return False
        self._cap = cap
        log.info("Opened camera device %s", self._config.device)
        return True

    def read(self) -> Optional[np.ndarray]:
        if self._cap is None and not self._open():
            return None

        assert self._cap is not None
        ok, frame = self._cap.read()
        if not ok or frame is None:
            log.warning("Failed to read frame from %s, reconnecting", self._config.device)
            self._cap.release()
            self._cap = None
            return None

        if self._config.crop is not None:
            x, y, w, h = self._config.crop
            frame = frame[y : y + h, x : x + w]

        return frame

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
