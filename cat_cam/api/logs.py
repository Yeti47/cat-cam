from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from .sse import sse_stream

router = APIRouter(tags=["logs"])


@router.get("/api/logs")
def get_logs(request: Request) -> dict:
    return {"lines": request.app.state.log_handler.recent()}


@router.get("/logs/stream")
def logs_stream(request: Request):
    state = request.app.state.shared
    return StreamingResponse(
        sse_stream(
            state.subscribe_logs,
            state.unsubscribe_logs,
            request.app.state.shutdown,
        ),
        media_type="text/event-stream",
    )
