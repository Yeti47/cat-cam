# cat-cam

Watches the DroidCam virtual camera feed pointed at the glass door and sends a
notification when a cat is detected outside, day or night.

## How it works

- Captures frames from a v4l2 device (`/dev/video1` by default — DroidCam's
  virtual camera) via OpenCV.
- Runs YOLOv8n (via `ultralytics`), filtered to the `cat` class, on CPU.
- If the frame is dark, it automatically switches to "night mode": applies
  CLAHE contrast enhancement and lowers the confidence threshold, so a cat
  lit only by ambient light isn't missed.
- Requires a few consecutive detecting frames before alerting (cuts down
  false positives), then stays quiet until the cat is gone from frame for
  `absence_reset_seconds`, at which point it re-arms — so a new arrival
  (the same cat coming back, or a different cat) notifies right away.
- Sends a desktop notification (`notify-send`) and/or a push notification
  via a self-hosted [ntfy](https://ntfy.sh) server reachable only over
  your Netbird VPN, each with a snapshot photo (bounding box drawn)
  attached.
- Serves a local [Web UI](#web-ui) with the live feed, a detection-zone
  editor, a browser flash/sound alert, live config tuning, and logs.

## Setup

Already done in this checkout, for reference / reinstalling elsewhere:

```bash
uv venv --python 3.12 .venv
uv pip install -e .
uv pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

(The CPU-only torch install avoids pulling multi-GB CUDA libraries that are
useless on this machine's AMD GPU — there's no GPU acceleration path used
here regardless, it's plain CPU inference and that's fast enough for
1-frame-per-second monitoring.)

The YOLOv8n weights (`yolov8n.pt`, ~6 MB) auto-download on first run.

## Configuration

Most of this is now easier to tune live from the [Web UI](#web-ui) below
(it writes back to `config.yaml` for you). Editing `config.yaml` by hand is
still there for the settings the UI doesn't cover:

- `camera.device` — check with `v4l2-ctl --list-devices` if DroidCam ever
  enumerates under a different `/dev/videoN`.
- `detection.confidence_day` / `confidence_night` / `night_brightness_threshold`
  / `consecutive_frames_required` / `absence_reset_seconds` — live-editable
  from the Web UI. If cats are being missed at night, lower
  `confidence_night` further or raise `night_brightness_threshold` so night
  mode kicks in more readily.
- `detection.zone` — set by dragging a rectangle in the Web UI rather than
  by hand; see [Web UI](#web-ui). Limits detection to that region of the
  frame, which also helps a nano-sized model's confidence when the cat is
  otherwise a small object in a wide frame.
- `camera.crop` — a static, always-applied pixel crop (unlike
  `detection.zone`, this also affects the streamed video and snapshots).
  Useful for cutting off black letterbox bars from a portrait phone stream
  before anything else sees the frame. Grab a test frame with
  `ffmpeg -f v4l2 -i /dev/video1 -frames:v 1 -update 1 test.jpg` and read
  off `[x, y, w, h]` pixel coordinates.
- `notify.desktop` / `notify.ntfy.enabled` — live-editable from the Web UI.
- `notify.ntfy.server` / `topic` — points at the self-hosted ntfy instance
  described below.

## Web UI

`cat-cam` serves a small local web page at **http://127.0.0.1:8090** (while
the service is running) with:

- A live view of the camera feed.
- A **detection zone** editor: drag out a rectangle over the video (drag
  its corners to resize, drag inside it to move), then "Save zone".
  Detection only runs inside that rectangle from then on — useful both to
  exclude irrelevant parts of the scene and to make a distant cat fill
  more of the region the model actually looks at. "Clear zone" goes back
  to scanning the full frame.
- The video border flashes and a beep plays in the browser the instant a
  cat is detected, on top of the desktop/ntfy notifications.
- Live-editable detection settings (confidence thresholds, night
  brightness threshold, consecutive-frames, absence reset) and the
  desktop/ntfy toggles — changes apply immediately, no restart needed, and
  are written back to `config.yaml` (comments and formatting preserved).
- A live-tailing log panel, so you don't need `journalctl` just to check
  what cat-cam is doing.

It's bound to `127.0.0.1` only, by design — there's no login, so it's only
ever reachable from this machine (open it on a second monitor here). Set
`web.enabled: false` in `config.yaml` to turn it off entirely.

## Notification server (self-hosted ntfy)

Runs as a Docker container (`cat-cam-ntfy`), bound only to this machine's
Netbird VPN interface (`<your-netbird-ip>`, port `28419`) — not the LAN or
the public internet. Only devices on the Netbird mesh (this machine, your
phone) can reach it, so snapshot photos never leave your own network or
touch a third-party server. The actual IP and topic are secrets kept in
`config.local.yaml` (gitignored, see `config.local.yaml.example`), not in
this file or `config.yaml`.

```bash
docker run -d \
  --name cat-cam-ntfy \
  --restart unless-stopped \
  -p <your-netbird-ip>:28419:80 \
  -v "$(pwd)/ntfy-server/cache:/var/cache/ntfy" \
  binwiederhier/ntfy serve \
    --cache-file /var/cache/ntfy/cache.db \
    --behind-proxy=false \
    --base-url http://<your-netbird-ip>:28419 \
    --attachment-cache-dir /var/cache/ntfy/attachments \
    --attachment-total-size-limit 1G \
    --attachment-file-size-limit 50M
```

`base-url` and `attachment-cache-dir` are both required for snapshot
attachments to work at all — without them ntfy silently rejects any
message with an attached image (`400: attachments not allowed`), while
plain text alerts still go through. This bit us once: a real detection
fired and logged "Notified", but the ntfy push never reached the phone
because the attachment was rejected server-side.

Message cache lives in `ntfy-server/cache/`, attachments in
`ntfy-server/cache/attachments/`. Docker's restart policy plus
`docker.service` being enabled at boot mean it comes back on its own
after a reboot or crash — no separate systemd unit needed.

If this machine's Netbird IP ever changes (check with `netbird status`),
update `notify.ntfy.server` in `config.local.yaml`, restart the container
with the new `-p <ip>:28419:80`, and restart `cat-cam.service`.

### Subscribe to notifications

1. Install the [ntfy app](https://ntfy.sh/app) (Android/iOS).
2. Add a custom server: `http://<your-netbird-ip>:28419` (the value from
   your `config.local.yaml`).
3. Subscribe to the topic from your `config.local.yaml`.
4. Make sure your phone is connected to the Netbird VPN.

## Running it

Installed as a systemd user service, so it starts on login and restarts on
failure:

```bash
systemctl --user status cat-cam.service
journalctl --user -u cat-cam.service -f   # tail logs
systemctl --user stop cat-cam.service     # stop
systemctl --user disable --now cat-cam.service  # stop + don't start on login
```

To run it manually instead (e.g. for debugging):

```bash
.venv/bin/python -m cat_cam.main --config config.yaml
```

## Snapshots

Saved to `snapshots/` with the detection box drawn on, named by timestamp.
Auto-deleted after `snapshot.retention_days` (default 14).
