from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from ultralytics import YOLO

from ..store import RuntimeSettings

log = logging.getLogger(__name__)

Zone = tuple[float, float, float, float]


@dataclass
class Detection:
    confidence: float
    box: tuple[int, int, int, int]  # x1, y1, x2, y2, in full-frame pixels
    is_night: bool


class CatDetector:
    def __init__(self, model: Path, class_name: str):
        # Ultralytics fetches a known asset name into this exact path on
        # first use, creating the directory, and reuses it thereafter.
        log.info("Loading model %s", model)
        self._model = YOLO(str(model))
        self._class_id = self._resolve_class_id(class_name)
        self._clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))

    def _resolve_class_id(self, class_name: str) -> int:
        for idx, name in self._model.names.items():
            if name == class_name:
                return idx
        raise ValueError(f"Model has no class named {class_name!r}; available: {self._model.names}")

    @staticmethod
    def _brightness(frame: np.ndarray) -> float:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return float(gray.mean())

    def _enhance_for_night(self, frame: np.ndarray) -> np.ndarray:
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        l = self._clahe.apply(l)
        lab = cv2.merge((l, a, b))
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    def detect(self, frame: np.ndarray, settings: RuntimeSettings) -> list[Detection]:
        """Run inference on `frame`, restricted to settings.zone if set.

        Boxes come back in full-frame coordinates regardless of the zone,
        so callers can draw them on the original frame.
        """
        zone: Optional[Zone] = settings.zone
        offset_x, offset_y = 0, 0
        region = frame
        if zone is not None:
            height, width = frame.shape[:2]
            zx, zy, zw, zh = zone
            offset_x = int(round(zx * width))
            offset_y = int(round(zy * height))
            region = frame[
                offset_y : offset_y + int(round(zh * height)),
                offset_x : offset_x + int(round(zw * width)),
            ]
            if region.size == 0:
                return []

        brightness = self._brightness(region)
        is_night = brightness < settings.night_brightness_threshold

        infer_frame = self._enhance_for_night(region) if is_night else region
        confidence = settings.confidence_night if is_night else settings.confidence_day

        results = self._model.predict(
            infer_frame,
            conf=confidence,
            classes=[self._class_id],
            verbose=False,
        )

        detections: list[Detection] = []
        for result in results:
            for box in result.boxes:
                xyxy = box.xyxy[0].tolist()
                detections.append(
                    Detection(
                        confidence=float(box.conf[0]),
                        box=(
                            int(xyxy[0]) + offset_x,
                            int(xyxy[1]) + offset_y,
                            int(xyxy[2]) + offset_x,
                            int(xyxy[3]) + offset_y,
                        ),
                        is_night=is_night,
                    )
                )

        if is_night:
            log.debug("Night mode active (brightness=%.1f, conf threshold=%.2f)", brightness, confidence)

        return detections
