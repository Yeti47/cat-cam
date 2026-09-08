# --- frontend: build the Svelte bundle ---
FROM node:22-slim AS frontend

WORKDIR /build
# Dependencies first, so source edits don't re-run npm ci.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build


# --- backend ---
FROM python:3.12-slim

# CPU-only torch, installed before anything else so ultralytics can't pull
# in the multi-GB CUDA wheels -- there's no GPU acceleration path here,
# plain CPU inference is fast enough for one frame per second.
RUN pip install --no-cache-dir \
      --index-url https://download.pytorch.org/whl/cpu \
      torch torchvision

WORKDIR /app

# Dependencies are resolved from pyproject alone, before the source is
# copied, so editing code doesn't reinstall the whole dependency tree.
COPY pyproject.toml ./
RUN mkdir -p cat_cam && touch cat_cam/__init__.py README.md \
 && pip install --no-cache-dir . \
 && pip uninstall -y cat-cam \
# ultralytics hard-depends on the GUI build of OpenCV (opencv-python),
# which gets pulled in regardless of our headless pin and then fails to
# import without libxcb. Both provide `cv2`, so swap it back out rather
# than installing X libraries this app has no use for.
 && pip uninstall -y opencv-python \
 && pip install --no-cache-dir --force-reinstall opencv-python-headless

# Ultralytics writes a settings file to ~/.config/Ultralytics by default,
# which fails for a container user without a home directory.
ENV YOLO_CONFIG_DIR=/app/.ultralytics

# Bake the weights in at build time so startup needs no network.
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

COPY cat_cam ./cat_cam
COPY --from=frontend /build/dist ./static

ENV CATCAM_DATA_DIR=/data \
    CATCAM_STATIC_DIR=/app/static \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1

# Run as uid/gid 1000 so files written into the data volume are owned by
# the host user rather than root.
RUN mkdir -p /data && chown -R 1000:1000 /app /data
USER 1000:1000

EXPOSE 8090

# A client that vanishes mid-stream (MJPEG feed, SSE tail) can otherwise
# leave a background task uvicorn waits on forever; bound it so SIGTERM
# always completes.
CMD ["uvicorn", "cat_cam.app:app", \
     "--host", "0.0.0.0", "--port", "8090", \
     "--timeout-graceful-shutdown", "5"]
