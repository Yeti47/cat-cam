from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/snapshots", tags=["snapshots"])


class SnapshotOut(BaseModel):
    id: str
    taken_at: datetime
    confidence: Optional[float]
    is_night: Optional[bool]


class SnapshotPage(BaseModel):
    items: list[SnapshotOut]
    total: int


@router.get("", response_model=SnapshotPage)
def list_snapshots(
    request: Request,
    limit: int = Query(60, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> SnapshotPage:
    infos = request.app.state.snapshots.list()
    page = infos[offset : offset + limit]
    return SnapshotPage(
        items=[
            SnapshotOut(
                id=i.id, taken_at=i.taken_at, confidence=i.confidence, is_night=i.is_night
            )
            for i in page
        ],
        total=len(infos),
    )


@router.get("/{snapshot_id}")
def get_snapshot(snapshot_id: str, request: Request):
    path = request.app.state.snapshots.path_for(snapshot_id)
    if path is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return FileResponse(path, media_type="image/jpeg")


@router.delete("/{snapshot_id}")
def delete_snapshot(snapshot_id: str, request: Request) -> dict:
    if not request.app.state.snapshots.delete(snapshot_id):
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return {"deleted": snapshot_id}
