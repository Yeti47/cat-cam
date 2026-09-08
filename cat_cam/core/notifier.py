from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import requests

log = logging.getLogger(__name__)


class Notifier:
    """Pushes to a self-hosted ntfy server.

    The server URL is deploy config (in Docker it's the compose service
    name); whether to send at all is a runtime setting, checked by the
    caller.
    """

    def __init__(self, server: str, topic: str):
        self._server = server
        self._topic = topic

    def notify(self, title: str, message: str, snapshot_path: Optional[Path] = None) -> None:
        url = f"{self._server.rstrip('/')}/{self._topic}"
        headers = {
            "Title": title.encode("ascii", "replace").decode(),
            "Tags": "cat",
            "Priority": "default",
        }
        try:
            if snapshot_path is not None and snapshot_path.exists():
                headers["Filename"] = snapshot_path.name
                headers["Message"] = message.encode("ascii", "replace").decode()
                with open(snapshot_path, "rb") as f:
                    resp = requests.put(url, data=f, headers=headers, timeout=10)
            else:
                resp = requests.post(url, data=message.encode("utf-8"), headers=headers, timeout=10)
            resp.raise_for_status()
        except requests.RequestException as exc:
            log.warning("ntfy notification failed: %s", exc)
