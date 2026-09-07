from __future__ import annotations

import json
import queue
import time
from pathlib import Path
from threading import Lock
from typing import Optional

_SSE_KEEPALIVE_SECONDS = 15

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

STATIC_DIR = Path(__file__).parent / "web_static"
_STREAM_FPS = 10.0


class ZonePayload(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    w: float = Field(gt=0, le=1)
    h: float = Field(gt=0, le=1)


class ConfigPayload(BaseModel):
    confidence_day: Optional[float] = Field(None, ge=0, le=1)
    confidence_night: Optional[float] = Field(None, ge=0, le=1)
    night_brightness_threshold: Optional[float] = Field(None, ge=0, le=255)
    consecutive_frames_required: Optional[int] = Field(None, ge=1)
    absence_reset_seconds: Optional[float] = Field(None, ge=0)
    notify_desktop: Optional[bool] = None
    notify_ntfy_enabled: Optional[bool] = None


def create_app(cat_cam_app, ring_handler) -> FastAPI:
    app = FastAPI()
    state = cat_cam_app.state
    config = cat_cam_app.config
    config_lock = Lock()

    @app.get("/")
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/stream.mjpg")
    def stream():
        def generate():
            while True:
                jpeg = state.get_jpeg()
                if jpeg is not None:
                    yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
                time.sleep(1.0 / _STREAM_FPS)

        return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=frame")

    @app.get("/events")
    def events():
        def generate():
            q = state.subscribe_detections()
            try:
                while True:
                    try:
                        event = q.get(timeout=_SSE_KEEPALIVE_SECONDS)
                    except queue.Empty:
                        # Also bounds how long a disconnected client's worker
                        # thread can stay blocked before it's reclaimed.
                        yield ": keep-alive\n\n"
                        continue
                    yield f"data: {json.dumps(event)}\n\n"
            finally:
                state.unsubscribe_detections(q)

        return StreamingResponse(generate(), media_type="text/event-stream")

    @app.get("/api/logs")
    def get_logs():
        return {"lines": ring_handler.recent()}

    @app.get("/logs/stream")
    def logs_stream():
        def generate():
            q = state.subscribe_logs()
            try:
                while True:
                    try:
                        line = q.get(timeout=_SSE_KEEPALIVE_SECONDS)
                    except queue.Empty:
                        yield ": keep-alive\n\n"
                        continue
                    yield f"data: {json.dumps(line)}\n\n"
            finally:
                state.unsubscribe_logs(q)

        return StreamingResponse(generate(), media_type="text/event-stream")

    @app.get("/api/zone")
    def get_zone():
        zone = config.detection.zone
        if zone is None:
            return {"zone": None}
        x, y, w, h = zone
        return {"zone": {"x": x, "y": y, "w": w, "h": h}}

    @app.post("/api/zone")
    def set_zone(payload: Optional[ZonePayload] = None):
        with config_lock:
            config.detection.zone = (payload.x, payload.y, payload.w, payload.h) if payload else None
            config.save()
        return get_zone()

    @app.get("/api/config")
    def get_config():
        d, n = config.detection, config.notify
        return {
            "confidence_day": d.confidence_day,
            "confidence_night": d.confidence_night,
            "night_brightness_threshold": d.night_brightness_threshold,
            "consecutive_frames_required": d.consecutive_frames_required,
            "absence_reset_seconds": d.absence_reset_seconds,
            "notify_desktop": n.desktop,
            "notify_ntfy_enabled": n.ntfy.enabled,
        }

    @app.post("/api/config")
    def set_config(payload: ConfigPayload):
        with config_lock:
            d, n = config.detection, config.notify
            updates = payload.model_dump(exclude_none=True)
            if "confidence_day" in updates:
                d.confidence_day = updates["confidence_day"]
            if "confidence_night" in updates:
                d.confidence_night = updates["confidence_night"]
            if "night_brightness_threshold" in updates:
                d.night_brightness_threshold = updates["night_brightness_threshold"]
            if "consecutive_frames_required" in updates:
                d.consecutive_frames_required = updates["consecutive_frames_required"]
            if "absence_reset_seconds" in updates:
                d.absence_reset_seconds = updates["absence_reset_seconds"]
            if "notify_desktop" in updates:
                n.desktop = updates["notify_desktop"]
            if "notify_ntfy_enabled" in updates:
                n.ntfy.enabled = updates["notify_ntfy_enabled"]
            config.save()
        return get_config()

    return app
