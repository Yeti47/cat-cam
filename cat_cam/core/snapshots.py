"""Snapshot storage.

Metadata lives in the filename rather than a sidecar index or database:
`cat_20260908_001500_c42n.jpg` is a 0.42-confidence night-mode hit. That
keeps listing stateless -- retention deletes can never leave an index
out of sync -- and makes confidence visible in the gallery, which is what
you actually want when tuning thresholds.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import cv2

log = logging.getLogger(__name__)

# cat_<date>_<time>[_c<confidence><night flag>].jpg
# The suffix is optional so snapshots taken before v2 still list, just
# without confidence.
_NAME_RE = re.compile(
    r"^cat_(?P<date>\d{8})_(?P<time>\d{6})(?:_c(?P<conf>\d{1,3})(?P<night>n?))?\.jpg$"
)


@dataclass
class SnapshotInfo:
    id: str
    taken_at: datetime
    confidence: Optional[float]
    is_night: Optional[bool]


def parse_name(name: str) -> Optional[SnapshotInfo]:
    match = _NAME_RE.match(name)
    if not match:
        return None
    try:
        taken_at = datetime.strptime(f"{match['date']}{match['time']}", "%Y%m%d%H%M%S")
    except ValueError:
        return None
    conf = match["conf"]
    return SnapshotInfo(
        id=name,
        taken_at=taken_at,
        confidence=int(conf) / 100 if conf is not None else None,
        is_night=bool(match["night"]) if conf is not None else None,
    )


class SnapshotStore:
    def __init__(self, directory: Path):
        self._dir = directory
        self._dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, snapshot_id: str) -> Optional[Path]:
        """Resolve an id to a path, rejecting anything that isn't a
        well-formed snapshot name (which also blocks path traversal)."""
        if parse_name(snapshot_id) is None:
            return None
        path = self._dir / snapshot_id
        return path if path.is_file() else None

    def save(self, frame, confidence: float, is_night: bool) -> Path:
        name = (
            f"cat_{datetime.now():%Y%m%d_%H%M%S}"
            f"_c{min(99, int(round(confidence * 100))):02d}{'n' if is_night else ''}.jpg"
        )
        path = self._dir / name
        cv2.imwrite(str(path), frame)
        return path

    def list(self) -> list[SnapshotInfo]:
        """Newest first."""
        infos = []
        for path in self._dir.glob("cat_*.jpg"):
            info = parse_name(path.name)
            if info is not None:
                infos.append(info)
        return sorted(infos, key=lambda i: i.taken_at, reverse=True)

    def delete(self, snapshot_id: str) -> bool:
        path = self.path_for(snapshot_id)
        if path is None:
            return False
        try:
            path.unlink()
            return True
        except OSError as exc:
            log.warning("Could not delete snapshot %s: %s", snapshot_id, exc)
            return False

    def cleanup(self, retention_days: int) -> None:
        cutoff = datetime.now() - timedelta(days=retention_days)
        for path in self._dir.glob("cat_*.jpg"):
            try:
                if datetime.fromtimestamp(path.stat().st_mtime) < cutoff:
                    path.unlink()
            except OSError as exc:
                log.warning("Could not clean up snapshot %s: %s", path, exc)
