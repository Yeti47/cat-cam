FROM python:3.12-slim

# CPU-only torch, installed before the project so ultralytics can't pull in
# the multi-GB CUDA wheels -- there's no GPU acceleration path here, plain
# CPU inference is fast enough for 1-frame-per-second monitoring.
RUN pip install --no-cache-dir \
      --index-url https://download.pytorch.org/whl/cpu \
      torch torchvision

WORKDIR /app

COPY pyproject.toml ./
COPY cat_cam ./cat_cam
# ultralytics hard-requires the GUI build of OpenCV (opencv-python), which
# gets pulled in regardless of our headless pin and then fails to import
# without libxcb/libGL. Both provide `cv2`, so swap it back out afterwards
# rather than installing X libraries this app has no use for.
RUN pip install --no-cache-dir . \
 && pip uninstall -y opencv-python \
 && pip install --no-cache-dir --force-reinstall opencv-python-headless

# Ultralytics writes a settings file to ~/.config/Ultralytics by default,
# which fails for a container user without a home directory.
ENV YOLO_CONFIG_DIR=/app/.ultralytics

# Bake the weights in at build time so startup needs no network and the
# image is self-contained. Lands in /app, matching the relative
# `detection.model` path in config.yaml.
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

# Run as uid/gid 1000 so files written through bind mounts (config.yaml
# edits from the web UI, new snapshots) stay owned by the host user rather
# than root.
RUN chown -R 1000:1000 /app
USER 1000:1000

EXPOSE 8090

CMD ["python", "-m", "cat_cam.main", "--config", "config.yaml"]
