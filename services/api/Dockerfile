# services/api — production image
#
# Phase 9 (PROJECT_HANDBOOK.md §6): multi-stage build so the runtime image
# never carries a C compiler, pip's build cache, or packages/shared's own
# source tree — only the wheels this service actually needs at import
# time.
#
# BUILD CONTEXT IS THE REPO ROOT, not services/api/ — this Dockerfile
# needs packages/shared (services/api/requirements.txt's
# `-e ../../packages/shared` line) to exist in the build context alongside
# services/api itself, and the two live as siblings only from the repo
# root. Build (and the equivalent in docker-compose.prod.yml) with:
#   docker build -f services/api/Dockerfile -t aegis-api .
# Building from inside services/api/ (context "." there) will fail with
# "packages/shared not found" — that's expected, not a bug in this file.
#
# syntax=docker/dockerfile:1

# ---- build stage --------------------------------------------------------
FROM python:3.12-slim AS builder

# Mirrors the exact relative layout PROJECT_HANDBOOK.md §5.3's local
# `cd services\api && pip install -r requirements.txt` already runs from,
# so requirements.txt's `-e ../../packages/shared` resolves identically
# here and on Sam's machine — no path rewriting needed.
WORKDIR /build
COPY packages/shared/ ./packages/shared/
COPY services/api/requirements.txt ./services/api/requirements.txt
WORKDIR /build/services/api

# `pip wheel` on a `-e <local path>` requirement builds a real wheel from
# that source tree (not an editable/.pth link back to /build) — the
# runtime stage below only ever sees built wheels, never needs
# packages/shared's source directory to exist inside it.
RUN pip install --no-cache-dir --upgrade pip \
    && pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# ---- runtime stage --------------------------------------------------------
FROM python:3.12-slim AS runtime

# psycopg2-binary (requirements.txt) ships its own libpq, so no extra apt
# packages are needed here — unlike services/ingestion's Dockerfile, which
# needs Ghostscript for camelot.
RUN useradd --create-home --uid 1000 appuser

WORKDIR /app
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir /wheels/*.whl \
    && rm -rf /wheels

# Mirrors services/api/alembic.ini's `script_location = %(here)s/../../migrations`
# (services/api/alembic.ini): two directories up from alembic.ini lands on
# migrations/, so the same two-level relationship is reproduced here —
# /app/services/api/alembic.ini -> /app/migrations — rather than
# flattening the layout and having to rewrite alembic.ini for Docker only.
COPY services/api/src ./services/api/src
COPY services/api/alembic.ini ./services/api/alembic.ini
COPY migrations ./migrations

RUN chown -R appuser:appuser /app
USER appuser

WORKDIR /app/services/api
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

# Hits the real readiness check (src/api/v1/routes/health.py's
# `GET /health/ready`), not bare liveness — a container that's up but
# can't reach Postgres should report unhealthy, not "ok". Needs `curl`,
# not present in python:3.12-slim by default.
USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health/ready || exit 1

# No `--reload` (that's `uvicorn`'s dev-only file-watcher) and bound to
# 0.0.0.0, not 127.0.0.1, so the container's published/mapped port
# actually reaches the process inside it.
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
