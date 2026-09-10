# cat-cam

Watches a camera pointed at the door and sends a notification when a cat is
detected outside, day or night.

## How it works

- Captures frames from any v4l2 device (`/dev/video*`) via OpenCV — a USB
  webcam, a CSI camera, or a virtual device fed by an IP-camera bridge or a
  phone streaming app. Set the device with `CATCAM_CAMERA_DEVICE`.
- Runs YOLOv8n (via `ultralytics`), filtered to the `cat` class, on CPU.
- If the frame is dark, it automatically switches to "night mode": applies
  CLAHE contrast enhancement and lowers the confidence threshold, so a cat
  lit only by ambient light isn't missed.
- Requires a few consecutive detecting frames before alerting (cuts down
  false positives), then stays quiet until the cat is gone from frame for
  the absence-reset window, at which point it re-arms — so a new arrival
  (the same cat coming back, or a different cat) notifies right away.
- Sends a push notification via a self-hosted [ntfy](https://ntfy.sh)
  server reachable only over your Netbird VPN, with a snapshot photo
  (bounding box drawn) attached.
- Serves a [Web UI](#web-ui) with the live feed, a detection-zone editor,
  a snapshot gallery, live config tuning, and logs.

## Architecture

```
frontend/          Svelte 5 + Vite + TypeScript, built to static files
cat_cam/
  app.py           ASGI app: routers, lifespan-managed pipeline
  settings.py      deploy config (env only)
  store.py         runtime config (JSON in the data volume)
  api/             config, stream, logs, snapshots routers
  core/            camera, detector, pipeline, notifier, snapshots, state
```

The backend is a plain ASGI service — `uvicorn cat_cam.app:app` — with no
CLI and no config file to edit. The capture/detect loop runs on a
background thread started by the app lifespan, handing frames to the web
layer through a shared state object.

The frontend is built in a Docker stage and served as static files by the
same FastAPI app, so there's one container, one origin, no CORS, and no
proxy rules for the MJPEG stream or SSE endpoints.

### Configuration: two tiers

| Tier | Source | Changes at runtime? | What |
| --- | --- | --- | --- |
| Deploy | `.env` → `CATCAM_*` env vars | No, restart required | Camera device and crop, ntfy server/topic, [model](#choosing-a-model), data dir, log level |
| Runtime | Web UI → `settings.json` in the data volume | Yes, applied live | Confidence thresholds, night brightness threshold, interval, consecutive frames, absence reset, detection zone, snapshot toggle/retention, notification mute |

The split is *where to send / what hardware* versus *how to detect*.
Nothing tunable lives in git, so adjusting a threshold or dragging the
detection zone never produces a repo diff — and a `git pull` on another
machine can't clobber locally tuned values.

There is deliberately **no user-editable config file**. The app owns
`settings.json` and rewrites it atomically.

## Setup

```bash
cp .env.example .env     # then fill in real values
docker compose up -d --build
```

`.env` holds both the compose-level values (Netbird IP the ntfy server
publishes on, camera device, the host's `video` group id) and the
`CATCAM_*` application settings. It's gitignored; `.env.example` is the
tracked template.

The first build is slow and lands at roughly 2 GB, almost entirely
CPU-only torch (no multi-GB CUDA wheels — inference here is plain CPU,
which is plenty for one frame per second).

### Choosing a model

Weights are not baked into the image. `CATCAM_YOLO_MODEL` names any asset
ultralytics publishes; it is fetched into `/data/models` on first start and
reused from there, so **changing model is a restart, not a rebuild**, and a
recreated container re-downloads nothing. A value containing `/` is treated
as a path instead, for a custom-trained checkpoint you bind-mount in.

Pick by scene, not by hardware — measured on a 12-thread CPU over
zone-cropped frames, even the largest is a fraction of the one-second
detection interval:

| Model | Inference | Use when |
| --- | --- | --- |
| `yolo26n.pt` | ~43 ms | The cat fills much of the detection zone |
| `yolo26s.pt` (default) | ~75 ms | Starting point |
| `yolo26m.pt` | ~188 ms | Still missing detections on `yolo26s` |

The default is `yolo26s`, not the faster nano, because nano turns out to be
fragile on a realistic outdoor scene rather than merely less accurate. On a
frame with a cat sitting a few metres from the window, nano scored 0.41
with a loose detection zone and produced **no box at all** once the zone
was tightened — the same frame `yolo26s` holds between 0.71 and 0.89 on,
whatever the zone. A detector whose answer depends that sharply on where
you drag the zone is not worth the 32 ms.

**If a cat that is plainly in frame produces no notification, change the
model before touching the confidence thresholds.** The threshold filters
boxes the model proposes; it cannot conjure one. A model too small for the
scene proposes no cat box at all, so lowering the threshold buys only false
positives from whatever else is in shot — watch for that signature in the
Snapshots gallery: hits at implausible confidences with no cat in them.

The trade-off for not baking weights is that a model's *first* start needs
network. It's one fetch ever per model, and `restart: unless-stopped`
covers a boot that comes up before the network does.

### Three things that look wrong but aren't

- **cat-cam publishes to `http://ntfy`, but ntfy's `--base-url` is the
  Netbird URL.** Both are deliberate. Publishing goes over the compose
  network, so the app container never needs to know the Netbird IP. But
  `--base-url` is what attachment links handed to your phone are built
  from, so it has to stay externally reachable. Don't "simplify" these to
  match.
- **The app binds `0.0.0.0` inside the container.** The
  `127.0.0.1:8090:8090` port publish is what actually keeps the feed off
  the network.
- **`pyproject.toml` pins `opencv-python-headless`, yet the Dockerfile
  uninstalls `opencv-python` anyway.** `ultralytics` hard-depends on the
  GUI build, which otherwise wins and crashes at import with
  `ImportError: libxcb.so.1`.

## Web UI

At **http://127.0.0.1:8090**, with four views:

- **Live** — the camera feed, plus the detection-zone editor. Drag on the
  feed to draw a zone, drag its corners to resize or its middle to move;
  it saves as you release. Detection then only runs inside that rectangle,
  which both excludes irrelevant parts of the scene and makes a distant
  cat fill more of the region the model actually looks at. "Hide zone"
  gets the overlay out of the way; "Clear zone" goes back to the full
  frame. The border flashes and a sound plays on every detection —
  browsers block audio until you've clicked the page once.
- **Snapshots** — gallery of saved detections, newest first, with
  timestamp and the confidence that triggered them. Click to enlarge,
  delete individually.
- **Config** — the runtime settings above, applied immediately with no
  restart, plus a read-only view of the deploy settings.
- **Logs** — live tail with filtering, so you don't need
  `docker compose logs` to see what cat-cam is doing.

It's bound to `127.0.0.1` only, by design — there's no login, so it's only
ever reachable from this machine.

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

Message cache lives in `ntfy-server/cache/`, bind-mounted so it survives
rebuilds.

If this machine's Netbird IP ever changes (check with `netbird status`),
update `NTFY_BIND_IP` and `NTFY_BASE_URL` in `.env` and run
`docker compose up -d`. cat-cam itself needs no change — it reaches ntfy
over the compose network.

### Subscribe to notifications

1. Install the [ntfy app](https://ntfy.sh/app) (Android/iOS).
2. Add a custom server: the `NTFY_BASE_URL` from your `.env`.
3. Subscribe to the `CATCAM_NTFY_TOPIC` from your `.env`.
4. Make sure your phone is connected to the Netbird VPN.

## Running it

```bash
docker compose up -d              # start (or apply .env / compose changes)
docker compose ps                 # status
docker compose logs -f cat-cam    # tail logs
docker compose restart cat-cam    # restart just the detector
docker compose down               # stop both services
docker compose up -d --build      # rebuild after a code change
```

Both services use `restart: unless-stopped`, so they come back after a
reboot or crash on their own.

Code changes need a rebuild — source and the frontend bundle are baked
into the image. Runtime settings never do: they live in the volume and
apply live.

## Data

Runtime settings, snapshots and downloaded model weights live in the
`cat-cam-data` named volume, not in the repo. Snapshots are named `cat_<date>_<time>_c<confidence>.jpg`
(with a trailing `n` for night-mode hits), so the gallery can show what
triggered each one without a database to keep in sync.

```bash
docker compose exec cat-cam ls /data/snapshots     # look around
docker compose cp cat-cam:/data/snapshots ./out    # pull them out
docker compose exec cat-cam cat /data/settings.json
```

Snapshots are deleted automatically after the retention window set in the
Config view.

## Development

The backend and frontend can run separately with hot reload:

```bash
# backend (needs the camera free, so stop the container first)
uv venv --python 3.12 .venv
uv pip install -e .
uv pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
CATCAM_DATA_DIR=./devdata .venv/bin/uvicorn cat_cam.app:app --port 8090 --reload

# frontend, proxying API calls to the backend above
cd frontend && npm install && npm run dev   # http://localhost:5173
```

`npm run build` type-checks with `svelte-check` before bundling.
