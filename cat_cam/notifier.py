from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Optional

import requests

from .config import NotifyConfig

log = logging.getLogger(__name__)


class Notifier:
    def __init__(self, config: NotifyConfig):
        self._config = config

    def notify(self, title: str, message: str, snapshot_path: Optional[Path] = None) -> None:
        if self._config.desktop:
            self._notify_desktop(title, message, snapshot_path)
        if self._config.ntfy.enabled:
            self._notify_ntfy(title, message, snapshot_path)

    def _notify_desktop(self, title: str, message: str, snapshot_path: Optional[Path]) -> None:
        cmd = ["notify-send", "--app-name=cat-cam", "-u", "normal"]
        if snapshot_path is not None:
            cmd += ["-i", str(snapshot_path)]
        cmd += [title, message]
        try:
            subprocess.run(cmd, check=True, timeout=5)
        except (subprocess.SubprocessError, FileNotFoundError) as exc:
            log.warning("Desktop notification failed: %s", exc)

    def _notify_ntfy(self, title: str, message: str, snapshot_path: Optional[Path]) -> None:
        url = f"{self._config.ntfy.server.rstrip('/')}/{self._config.ntfy.topic}"
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
