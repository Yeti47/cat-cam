from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ruamel.yaml import YAML

_yaml = YAML()
_yaml.preserve_quotes = True


def _deep_merge(base: dict, override: dict) -> dict:
    """Merge `override` onto a shallow copy of `base`, recursing into
    nested dicts. Used to layer config.local.yaml (gitignored secrets)
    on top of config.yaml without mutating either."""
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


@dataclass
class NtfyConfig:
    enabled: bool = True
    server: str = "https://ntfy.sh"
    topic: str = "catcam-CHANGE-ME"


@dataclass
class NotifyConfig:
    desktop: bool = True
    ntfy: NtfyConfig = field(default_factory=NtfyConfig)


@dataclass
class CameraConfig:
    device: str = "/dev/video1"
    crop: Optional[tuple[int, int, int, int]] = None


@dataclass
class DetectionConfig:
    model: str = "yolov8n.pt"
    class_name: str = "cat"
    confidence_day: float = 0.5
    confidence_night: float = 0.25
    night_brightness_threshold: float = 60.0
    interval_seconds: float = 1.0
    consecutive_frames_required: int = 2
    absence_reset_seconds: float = 30.0
    # Normalized (x, y, w, h) in 0..1 of the (camera.crop-applied) frame.
    # Detection only runs inside this rect; null means the full frame.
    # Set/edited from the web UI's zone editor.
    zone: Optional[tuple[float, float, float, float]] = None


@dataclass
class SnapshotConfig:
    enabled: bool = True
    dir: str = "snapshots"
    retention_days: int = 14


@dataclass
class WebConfig:
    enabled: bool = True
    # Bound to localhost only by design -- the live feed has no
    # authentication, so it must never be reachable off this machine.
    host: str = "127.0.0.1"
    port: int = 8090


@dataclass
class Config:
    camera: CameraConfig = field(default_factory=CameraConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    notify: NotifyConfig = field(default_factory=NotifyConfig)
    snapshot: SnapshotConfig = field(default_factory=SnapshotConfig)
    web: WebConfig = field(default_factory=WebConfig)
    logging_level: str = "INFO"
    _path: Optional[Path] = field(default=None, repr=False, compare=False)
    _raw: Optional[dict] = field(default=None, repr=False, compare=False)

    @staticmethod
    def load(path: str | Path) -> "Config":
        path = Path(path)
        raw = _yaml.load(path.read_text()) or {}

        # config.local.yaml (gitignored) layers secrets like the ntfy
        # server/topic on top, so they never need to live in config.yaml.
        # `raw` (without this overlay) is what save() writes back to, so
        # local secrets never leak into the tracked file.
        local_path = path.parent / "config.local.yaml"
        effective = raw
        if local_path.exists():
            local_raw = _yaml.load(local_path.read_text()) or {}
            effective = _deep_merge(raw, local_raw)

        cam_raw = effective.get("camera", {})
        crop = cam_raw.get("crop")
        camera = CameraConfig(
            device=cam_raw.get("device", CameraConfig.device),
            crop=tuple(crop) if crop else None,
        )

        det_raw = effective.get("detection", {})
        zone = det_raw.get("zone")
        detection = DetectionConfig(
            model=det_raw.get("model", DetectionConfig.model),
            class_name=det_raw.get("class_name", DetectionConfig.class_name),
            confidence_day=float(det_raw.get("confidence_day", DetectionConfig.confidence_day)),
            confidence_night=float(det_raw.get("confidence_night", DetectionConfig.confidence_night)),
            night_brightness_threshold=float(
                det_raw.get("night_brightness_threshold", DetectionConfig.night_brightness_threshold)
            ),
            interval_seconds=float(det_raw.get("interval_seconds", DetectionConfig.interval_seconds)),
            consecutive_frames_required=int(
                det_raw.get("consecutive_frames_required", DetectionConfig.consecutive_frames_required)
            ),
            absence_reset_seconds=float(
                det_raw.get("absence_reset_seconds", DetectionConfig.absence_reset_seconds)
            ),
            zone=tuple(float(v) for v in zone) if zone else None,
        )

        notify_raw = effective.get("notify", {})
        ntfy_raw = notify_raw.get("ntfy", {})
        notify = NotifyConfig(
            desktop=bool(notify_raw.get("desktop", NotifyConfig.desktop)),
            ntfy=NtfyConfig(
                enabled=bool(ntfy_raw.get("enabled", NtfyConfig.enabled)),
                server=ntfy_raw.get("server", NtfyConfig.server),
                topic=ntfy_raw.get("topic", NtfyConfig.topic),
            ),
        )

        snap_raw = effective.get("snapshot", {})
        snapshot = SnapshotConfig(
            enabled=bool(snap_raw.get("enabled", SnapshotConfig.enabled)),
            dir=snap_raw.get("dir", SnapshotConfig.dir),
            retention_days=int(snap_raw.get("retention_days", SnapshotConfig.retention_days)),
        )

        web_raw = effective.get("web", {})
        web = WebConfig(
            enabled=bool(web_raw.get("enabled", WebConfig.enabled)),
            host=web_raw.get("host", WebConfig.host),
            port=int(web_raw.get("port", WebConfig.port)),
        )

        logging_level = effective.get("logging", {}).get("level", "INFO")

        return Config(
            camera=camera,
            detection=detection,
            notify=notify,
            snapshot=snapshot,
            web=web,
            logging_level=logging_level,
            _path=path,
            _raw=raw,
        )

    def save(self, path: Optional[str | Path] = None) -> None:
        """Write live values back to the YAML file, preserving comments
        and formatting via ruamel's round-trip mode."""
        target = Path(path) if path is not None else self._path
        if target is None:
            raise ValueError("Config has no associated path to save to")

        raw = self._raw if self._raw is not None else {}

        det = raw.setdefault("detection", {})
        det["confidence_day"] = self.detection.confidence_day
        det["confidence_night"] = self.detection.confidence_night
        det["night_brightness_threshold"] = self.detection.night_brightness_threshold
        det["consecutive_frames_required"] = self.detection.consecutive_frames_required
        det["absence_reset_seconds"] = self.detection.absence_reset_seconds
        det["zone"] = list(self.detection.zone) if self.detection.zone else None

        notify = raw.setdefault("notify", {})
        notify["desktop"] = self.notify.desktop
        ntfy = notify.setdefault("ntfy", {})
        ntfy["enabled"] = self.notify.ntfy.enabled

        with target.open("w") as f:
            _yaml.dump(raw, f)

        self._raw = raw
        self._path = target
