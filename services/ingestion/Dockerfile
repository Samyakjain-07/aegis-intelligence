# services/ingestion — production image (Celery worker)
#
# Phase 9 (PROJECT_HANDBOOK.md §6). Same build-context requirement as
# services/api/Dockerfile — this must be built from the REPO ROOT, not
# services/ingestion/, so packages/shared is visible:
#   docker build -f services/ingestion/Dockerfile -t aegis-ingestion .
#
# syntax=docker/dockerfile:1

# ---- build stage --------------------------------------------------------
FROM python:3.12-slim AS builder

# camelot-py[cv]'s build (and its opencv-python-headless dependency) needs
# a C/C++ toolchain to compile from source on slim's minimal base —
# services/ingestion/requirements.txt's own header comment already flags
# Ghostscript as a manual OS-level dependency on Windows; build-essential
# here is that same class of requirement, just for Debian instead.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY packages/shared/ ./packages/shared/
COPY services/ingestion/requirements.txt ./services/ingestion/requirements.txt
WORKDIR /build/services/ingestion
RUN pip install --no-cache-dir --upgrade pip \
    && pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# ---- runtime stage --------------------------------------------------------
FROM python:3.12-slim AS runtime

# Ghostscript: camelot's actual PDF-table extraction shells out to `gs` at
# RUNTIME, not import time — this is the same manual OS-level dependency
# services/ingestion/requirements.txt's header comment calls out for local
# Windows dev, reproduced here as a real apt package instead of a manual
# step, since a container has no "Sam installs it once" equivalent.
# libgl1 + libglib2.0-0: opencv-python-headless (camelot-py[cv]'s own
# dependency) still dlopens a handful of shared libraries a truly headless
# base image doesn't ship, even though it doesn't need an actual display.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ghostscript libgl1 libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 appuser

WORKDIR /app
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir /wheels/*.whl \
    && rm -rf /wheels

COPY services/ingestion/src ./services/ingestion/src

RUN chown -R appuser:appuser /app
USER appuser

WORKDIR /app/services/ingestion
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# `celery inspect ping` against this worker's own hostname is the
# standard way to healthcheck a Celery worker — there's no HTTP port to
# curl (unlike services/api's Dockerfile).
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD celery -A src.infra.celery_app inspect ping -d celery@$HOSTNAME || exit 1

# Deliberately NO `--pool=solo` here — that flag exists purely to work
# around native Windows's lack of `os.fork()`
# (PROJECT_HANDBOOK.md §5/CLAUDE.md §8's Windows-specific note, and
# services/ingestion/src/infra/celery_app.py's own docstring). This image
# runs on Linux, where the default `prefork` pool works normally and is
# more performant than solo's single-threaded queue — using `--pool=solo`
# here would silently throw away all of prefork's concurrency for no
# reason. `--concurrency` is left at Celery's own default (CPU count);
# override via a `command:` override in docker-compose.prod.yml / the
# ECS task definition if a specific worker size is needed.
CMD ["celery", "-A", "src.infra.celery_app", "worker", "--loglevel=info"]
