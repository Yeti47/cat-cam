"""Deploy-time settings: hardware, notification target, paths.

These come from the environment only and never change while the process
is running. Anything a user would want to tune while watching the feed
belongs in `cat_cam.store` instead, where the Web UI owns it.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CATCAM_", extra="ignore")

    # Camera
    camera_device: str = "/dev/video1"
    # Static (x, y, w, h) pixel crop applied to every frame before anything
    # else sees it -- e.g. to trim letterbox bars when the source's aspect
    # ratio doesn't match the capture resolution. Distinct from the
    # detection zone, which only limits where the model looks.
    # Accepts "0,60,1280,600" or a JSON list.
    camera_crop: Optional[tuple[int, int, int, int]] = None

    # Model
    yolo_model: str = "yolov8n.pt"
    class_name: str = "cat"

    # Notification target. Whether to send is a runtime setting; where to
    # send is infrastructure, so it lives here.
    ntfy_enabled: bool = True
    ntfy_server: str = "http://ntfy"
    ntfy_topic: str = "catcam-CHANGE-ME"

    # Writable state: settings.json + snapshots/
    data_dir: Path = Path("/data")

    # Built frontend bundle. This is a container artifact (the Docker
    # frontend stage writes it here); a bare-metal backend run without it
    # simply serves the API, with the Vite dev server providing the UI.
    static_dir: Path = Path("/app/static")

    log_level: str = "INFO"

    @field_validator("camera_crop", mode="before")
    @classmethod
    def _parse_crop(cls, value):
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
            if "," in value:
                return tuple(int(part) for part in value.split(","))
        return value

    @property
    def settings_file(self) -> Path:
        return self.data_dir / "settings.json"

    @property
    def snapshot_dir(self) -> Path:
        return self.data_dir / "snapshots"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
