"""Runtime settings: everything tunable from the Web UI.

Persisted as JSON in the data volume, owned entirely by the application --
there is no user-editable config file, and nothing here lives in git.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

log = logging.getLogger(__name__)


class RuntimeSettings(BaseModel):
    model_config = {"frozen": True}

    # Confidence threshold in normal (daytime/bright) conditions.
    confidence_day: float = Field(default=0.32, ge=0, le=1)
    # Used once the scene is judged dark. Lower = more sensitive, but more
    # prone to false positives.
    confidence_night: float = Field(default=0.18, ge=0, le=1)
    # Mean pixel brightness (0-255) below which night mode kicks in: CLAHE
    # contrast enhancement plus the night confidence threshold. Note this
    # average is taken over the detection zone, so a tight zone around the
    # door avoids bright indoor floor/frame skewing it upward and keeping
    # night mode from ever triggering.
    night_brightness_threshold: float = Field(default=60.0, ge=0, le=255)
    # How often to run detection. Frames are captured faster than this for
    # a smooth live feed; only inference is throttled.
    interval_seconds: float = Field(default=1.0, gt=0, le=60)
    # Consecutive detecting frames required before alerting, to filter
    # one-off false positives.
    consecutive_frames_required: int = Field(default=2, ge=1, le=30)
    # If nothing is detected for this long, consider the cat gone and
    # re-arm, so a new arrival notifies right away.
    absence_reset_seconds: float = Field(default=30.0, ge=0)
    # Normalized (x, y, w, h) in 0..1. Detection runs only inside this
    # rect; null means the full frame.
    zone: Optional[tuple[float, float, float, float]] = None

    snapshots_enabled: bool = True
    snapshot_retention_days: int = Field(default=14, ge=1, le=365)
    # Mute switch for outgoing pushes. Where they go is deploy config.
    notifications_enabled: bool = True


class SettingsStore:
    """Thread-safe accessor for RuntimeSettings backed by a JSON file.

    The capture/detect loop calls get() every iteration, so reads must be
    cheap and never block on disk -- the current value is held in memory
    and only writes touch the filesystem.
    """

    def __init__(self, path: Path):
        self._path = path
        self._lock = threading.Lock()
        self._settings = self._load()

    def _load(self) -> RuntimeSettings:
        if not self._path.exists():
            log.info("No settings file at %s, starting from defaults", self._path)
            settings = RuntimeSettings()
            self._write(settings)
            return settings
        try:
            raw = json.loads(self._path.read_text())
            return RuntimeSettings.model_validate(raw)
        except (OSError, ValueError) as exc:
            # Never fail to start because of a corrupt settings file -- the
            # detector is the point of the service, and defaults still work.
            log.warning("Could not read %s (%s), falling back to defaults", self._path, exc)
            return RuntimeSettings()

    def _write(self, settings: RuntimeSettings) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic replace, so a crash mid-write can't truncate the file.
        tmp = self._path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(settings.model_dump(), indent=2) + "\n")
        os.replace(tmp, self._path)

    def get(self) -> RuntimeSettings:
        with self._lock:
            return self._settings

    def patch(self, updates: dict) -> RuntimeSettings:
        """Apply a partial update, validate the result, persist it."""
        with self._lock:
            merged = self._settings.model_dump() | updates
            settings = RuntimeSettings.model_validate(merged)
            self._write(settings)
            self._settings = settings
            log.info("Settings updated: %s", ", ".join(sorted(updates)))
            return settings
