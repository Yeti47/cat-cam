from __future__ import annotations

import logging
from typing import Optional

import cv2
import numpy as np

log = logging.getLogger(__name__)

Crop = tuple[int, int, int, int]


class Camera:
    """Thin wrapper around a v4l2 video device, with automatic reconnect
    if the stream drops.

    Any `/dev/video*` source works: a USB webcam, a CSI camera, or a
    virtual device fed by something else (an IP camera bridge, a phone
    streaming app). Reconnect matters most for virtual devices, whose
    feed can disappear without the node going away."""

    def __init__(self, device: str, crop: Optional[Crop] = None):
        self._device = device
        self._crop = crop
        self._cap: Optional[cv2.VideoCapture] = None

    def _open(self) -> bool:
        cap = cv2.VideoCapture(self._device, cv2.CAP_V4L2)
        if not cap.isOpened():
            cap.release()
            return False
        self._cap = cap
        log.info("Opened camera device %s", self._device)
        return True

    def read(self) -> Optional[np.ndarray]:
        if self._cap is None and not self._open():
            return None

        assert self._cap is not None
        ok, frame = self._cap.read()
        if not ok or frame is None:
            log.warning("Failed to read frame from %s, reconnecting", self._device)
            self._cap.release()
            self._cap = None
            return None

        if self._crop is not None:
            x, y, w, h = self._crop
            frame = frame[y : y + h, x : x + w]

        return frame

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
