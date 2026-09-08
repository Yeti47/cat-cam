"""ASGI application entry point.

Run with: uvicorn cat_cam.app:app --host 0.0.0.0 --port 8090

There is no CLI: deploy config comes from the environment, runtime config
from the Web UI. The capture/detect pipeline runs on a background thread
owned by the app lifespan.
"""

from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .api import config as config_routes
from .api import logs as log_routes
from .api import snapshots as snapshot_routes
from .api import stream as stream_routes
from .core.pipeline import Pipeline
from .core.snapshots import SnapshotStore
from .core.state import SharedState
from .logbuffer import RingBufferHandler
from .settings import get_settings
from .store import SettingsStore

log = logging.getLogger("cat_cam")

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def _configure_logging(level: str, state: SharedState) -> RingBufferHandler:
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO), format=LOG_FORMAT)
    handler = RingBufferHandler(state)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logging.getLogger("cat_cam").addHandler(handler)
    return handler


def create_app() -> FastAPI:
    settings = get_settings()
    shared = SharedState()
    log_handler = _configure_logging(settings.log_level, shared)
    store = SettingsStore(settings.settings_file)
    snapshots = SnapshotStore(settings.snapshot_dir)
    pipeline = Pipeline(settings, store, shared)

    # Signals in-flight streaming responses to finish promptly. Without it
    # their worker threads keep the process alive past the container's stop
    # deadline and it gets SIGKILLed.
    shutdown = threading.Event()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        pipeline.start()
        try:
            yield
        finally:
            shutdown.set()
            pipeline.stop()

    app = FastAPI(title="cat-cam", lifespan=lifespan)
    app.state.shutdown = shutdown
    app.state.settings = settings
    app.state.store = store
    app.state.shared = shared
    app.state.snapshots = snapshots
    app.state.log_handler = log_handler
    app.state.pipeline = pipeline

    app.include_router(config_routes.router)
    app.include_router(snapshot_routes.router)
    app.include_router(stream_routes.router)
    app.include_router(log_routes.router)

    if settings.static_dir.is_dir():
        # html=True serves index.html at "/". Mounted last so it can't
        # shadow API routes.
        app.mount("/", StaticFiles(directory=settings.static_dir, html=True), name="frontend")
    else:
        log.warning("No built frontend at %s -- serving API only", settings.static_dir)

        @app.get("/")
        def no_frontend() -> dict:
            return {"detail": "Frontend not built. Run `npm run build` in frontend/."}

    return app


app = create_app()
