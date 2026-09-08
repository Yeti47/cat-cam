from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from ..store import RuntimeSettings

router = APIRouter(prefix="/api", tags=["config"])


class SettingsPatch(BaseModel):
    """All fields optional: a PATCH only carries what changed."""

    model_config = {"extra": "forbid"}

    confidence_day: Optional[float] = Field(None, ge=0, le=1)
    confidence_night: Optional[float] = Field(None, ge=0, le=1)
    night_brightness_threshold: Optional[float] = Field(None, ge=0, le=255)
    interval_seconds: Optional[float] = Field(None, gt=0, le=60)
    consecutive_frames_required: Optional[int] = Field(None, ge=1, le=30)
    absence_reset_seconds: Optional[float] = Field(None, ge=0)
    zone: Optional[tuple[float, float, float, float]] = None
    snapshots_enabled: Optional[bool] = None
    snapshot_retention_days: Optional[int] = Field(None, ge=1, le=365)
    notifications_enabled: Optional[bool] = None
    # Sent explicitly to clear the zone, since None otherwise just means
    # "not included in this patch".
    clear_zone: bool = False


class DeployInfo(BaseModel):
    """Read-only view of env-supplied settings, so the UI can show what
    it cannot change."""

    camera_device: str
    camera_crop: Optional[tuple[int, int, int, int]]
    yolo_model: str
    class_name: str
    ntfy_enabled: bool
    ntfy_server: str
    ntfy_topic: str


@router.get("/config", response_model=RuntimeSettings)
def get_config(request: Request) -> RuntimeSettings:
    return request.app.state.store.get()


@router.patch("/config", response_model=RuntimeSettings)
def patch_config(payload: SettingsPatch, request: Request) -> RuntimeSettings:
    updates = payload.model_dump(exclude_none=True, exclude={"clear_zone"})
    if payload.clear_zone:
        updates["zone"] = None
    return request.app.state.store.patch(updates)


@router.get("/deploy-info", response_model=DeployInfo)
def get_deploy_info(request: Request) -> DeployInfo:
    settings = request.app.state.settings
    return DeployInfo(
        camera_device=settings.camera_device,
        camera_crop=settings.camera_crop,
        yolo_model=settings.yolo_model,
        class_name=settings.class_name,
        ntfy_enabled=settings.ntfy_enabled,
        ntfy_server=settings.ntfy_server,
        ntfy_topic=settings.ntfy_topic,
    )
