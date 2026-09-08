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
- Sends a push notification via a self-hosted [ntfy](https://ntfy.sh)
  server reachable only over your Netbird VPN, with a snapshot photo
  (bounding box drawn) attached. (Desktop `notify-send` notifications are
  also supported, but off by default — see `notify.desktop` below.)
- Serves a local [Web UI](#web-ui) with the live feed, a detection-zone
  editor, a browser flash/sound alert, live config tuning, and logs.

## Setup

Everything runs as a `docker compose` stack — cat-cam plus its own ntfy
server. There's no systemd unit and no local virtualenv to maintain.

```bash
cp .env.example .env                          # then fill in real values
cp config.local.yaml.example config.local.yaml # then fill in the ntfy topic
docker compose up -d --build
```

`.env` holds infrastructure values compose interpolates (the Netbird IP the
ntfy server publishes on, the camera device, the host's `video` group id).
`config.local.yaml` holds app-level secrets — the ntfy topic. Both are
gitignored; the `.example` files next to them show the structure.

The first build is slow and lands at roughly 2 GB: it installs CPU-only
torch (no multi-GB CUDA wheels — inference here is plain CPU, which is
plenty for one frame per second) and bakes the YOLOv8n weights into the
image so startup needs no network.

### Two things that look wrong but aren't

- **cat-cam publishes to `http://ntfy`, but ntfy's `--base-url` is the
  Netbird URL.** Both are deliberate. Publishing goes over the compose
  network, so the app container never needs to know the Netbird IP. But
  `--base-url` is what attachment links handed to your phone are built
  from, so it has to stay externally reachable. Don't "simplify" these to
  match.
- **`web.host` is `127.0.0.1` in `config.yaml`, but the container sets
  `CATCAM_WEB_HOST=0.0.0.0`.** Inside the container it must bind all
  interfaces; the `127.0.0.1:8090:8090` port publish is what actually keeps
  the feed off the network. The config keeps the safe default so a
  bare-metal run doesn't accidentally expose the camera.

## Configuration

Values are layered, highest precedence first:

| Layer | File | Tracked? | Holds |
| --- | --- | --- | --- |
| Env vars | compose `environment:` | yes | Only what must differ in Docker: `CATCAM_WEB_HOST`, `CATCAM_NTFY_SERVER` |
| Local overrides | `config.local.yaml` | **no** | App secrets — the ntfy topic |
| Base config | `config.yaml` | yes | Everything else |

(`.env` is a fourth, separate thing: it's read by *compose itself*, not the
app, for port bindings and device paths.)

Most tuning is easier from the [Web UI](#web-ui) below, which writes back to
`config.yaml` for you — preserving its comments, and never writing secrets
from the layers above into it. Editing `config.yaml` by hand is still there
for the settings the UI doesn't cover:

- `camera.device` — check with `v4l2-ctl --list-devices` if DroidCam ever
  enumerates under a different `/dev/videoN`. Also update `CAMERA_DEVICE`
  in `.env`, since the device is passed into the container by path.
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
- `notify.desktop` — `notify-send` desktop notifications. Off by default:
  there's no DBUS session inside the container, so this only does anything
  for a bare-metal run. The Web UI's flash + beep replaces it.
- `notify.ntfy.enabled` — live-editable from the Web UI.
- `notify.ntfy.server` / `topic` — the self-hosted ntfy instance described
  below. `topic` belongs in `config.local.yaml`; `server` is overridden to
  the compose hostname inside the container.

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
  cat is detected, on top of the ntfy push.
- Live-editable detection settings (confidence thresholds, night
  brightness threshold, consecutive-frames, absence reset) and the
  notification toggles — changes apply immediately, no restart needed, and
  are written back to `config.yaml` (comments and formatting preserved).
- A live-tailing log panel, so you don't need `docker compose logs` just to
  check what cat-cam is doing.

It's bound to `127.0.0.1` only, by design — there's no login, so it's only
ever reachable from this machine (open it on a second monitor here). Set
`web.enabled: false` in `config.yaml` to turn it off entirely.

## Notification server (self-hosted ntfy)

The `ntfy` service in `docker-compose.yml`, published only on this
machine's Netbird VPN interface (`${NTFY_BIND_IP}:${NTFY_PORT}` from
`.env`) — not the LAN or the public internet. Only devices on the Netbird
mesh (this machine, your phone) can reach it, so snapshot photos never
leave your own network or touch a third-party server.

`--base-url` and `--attachment-cache-dir` are both required for snapshot
attachments to work at all — without them ntfy silently rejects any
message with an attached image (`400: attachments not allowed`), while
plain text alerts still go through. This bit us once: a real detection
fired and logged "Notified", but the ntfy push never reached the phone
because the attachment was rejected server-side.

Message cache lives in `ntfy-server/cache/`, attachments in
`ntfy-server/cache/attachments/`, both bind-mounted so they survive
container rebuilds.

If this machine's Netbird IP ever changes (check with `netbird status`),
update `NTFY_BIND_IP` and `NTFY_BASE_URL` in `.env` and run
`docker compose up -d` to recreate the containers. cat-cam itself needs no
change — it reaches ntfy over the compose network.

### Subscribe to notifications

1. Install the [ntfy app](https://ntfy.sh/app) (Android/iOS).
2. Add a custom server: the `NTFY_BASE_URL` from your `.env`.
3. Subscribe to the topic from your `config.local.yaml`.
4. Make sure your phone is connected to the Netbird VPN.

## Running it

```bash
docker compose up -d              # start (or apply config/compose changes)
docker compose ps                 # status
docker compose logs -f cat-cam    # tail logs
docker compose restart cat-cam    # restart just the detector
docker compose down               # stop both services
docker compose up -d --build      # rebuild after a code change
```

Both services use `restart: unless-stopped`, so they come back after a
reboot or crash on their own.

Code changes need a rebuild (`--build`) — the source is baked into the
image, not mounted. Config and snapshot changes don't: those are bind
mounts, and detection settings edited in the Web UI apply live.

To run bare-metal instead (e.g. for debugging with a debugger attached):

```bash
uv venv --python 3.12 .venv
uv pip install -e .
uv pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
.venv/bin/python -m cat_cam.main --config config.yaml
```

That path reads `config.local.yaml` directly with no env overrides, so it
talks to ntfy over the Netbird IP and binds the Web UI to `127.0.0.1`.

## Snapshots

Saved to `snapshots/` with the detection box drawn on, named by timestamp.
Auto-deleted after `snapshot.retention_days` (default 14).
