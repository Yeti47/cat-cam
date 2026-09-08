from __future__ import annotations

import time

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from .sse import sse_stream

router = APIRouter(tags=["stream"])

_STREAM_FPS = 10.0


@router.get("/stream.mjpg")
def stream(request: Request):
    state = request.app.state.shared
    shutdown = request.app.state.shutdown

    def generate():
        while not shutdown.is_set():
            jpeg = state.get_jpeg()
            if jpeg is not None:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
            time.sleep(1.0 / _STREAM_FPS)

    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=frame")


@router.get("/events")
def events(request: Request):
    state = request.app.state.shared
    return StreamingResponse(
        sse_stream(
            state.subscribe_detections,
            state.unsubscribe_detections,
            request.app.state.shutdown,
        ),
        media_type="text/event-stream",
    )
