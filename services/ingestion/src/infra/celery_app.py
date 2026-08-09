"""Shared Celery app instance for `services/ingestion` (the consumer/worker
side).

A genuinely separate `Celery(...)` instance from
`services/api/src/infra/celery_app.py`'s -- the two services never import
each other's Python code (see `CLAUDE.md` §1 / `docs/architecture.md` §3's
"decoupled, independently-scaling services" principle, already established
for exactly this pair of files back in Phase 4). They agree only by
convention: the same `REDIS_URL` broker/backend, and the same task name
(`"ingest_document"`) -- Celery routes a task purely by that string name
once it's on the broker, so a worker started from here picks up anything
already enqueued by the Phase 4 API-side stub with no rename needed.

`include=["src.tasks.ingest_document"]` is what actually registers the
real task body with this app before the worker starts consuming --
without it, `celery -A src.infra.celery_app worker` would come up with an
empty task registry and reject `"ingest_document"` messages as unknown.
"""
from __future__ import annotations

import os

from celery import Celery
from dotenv import load_dotenv

load_dotenv()

REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "aegis_ingestion",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["src.tasks.ingest_document"],
)
