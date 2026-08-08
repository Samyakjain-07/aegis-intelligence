"""Shared Celery app instance for `services/api` (the producer side).

Phase 4 (`PROJECT_HANDBOOK.md`) needs somewhere for `POST /documents` to
`.delay()` a task -- this is that instance, plus a genuinely-registered
no-op placeholder task (`ingest_document`) so the call is a real enqueue
against Redis, not a faked one. Real ingestion logic replaces this task's
*body* in Phase 5, inside `services/ingestion/src/tasks/ingest_document.py`
-- registered under the exact same task name (`"ingest_document"`) so a
worker started from `services/ingestion` picks up anything already queued
by this stub without a rename. `services/ingestion` gets its own
`celery_app.py` pointed at the same Redis broker in Phase 5 (per
`docs/Financial_RAG_Project_Structure.md`'s planned layout); this module is
API-side only (the producer), not shared by import between the two
services -- they're deliberately decoupled (`CLAUDE.md` §1/`docs/
architecture.md` §3), so the two Celery app instances only ever agree by
convention (same broker URL, same task name), never by sharing Python code.
"""
from __future__ import annotations

import os

from celery import Celery
from dotenv import load_dotenv

load_dotenv()

REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery("aegis_api", broker=REDIS_URL, backend=REDIS_URL)


@celery_app.task(name="ingest_document")
def ingest_document_stub(document_id: str) -> dict[str, str]:
    """No-op placeholder. Doesn't parse, chunk, embed, or write anything --
    it exists so `POST /documents` has a real Celery task to enqueue
    against, proving the async ingestion hand-off works end-to-end, before
    Phase 5 gives this task name a real body (in `services/ingestion`, not
    here).
    """
    return {"document_id": document_id, "status": "stub-noop"}
