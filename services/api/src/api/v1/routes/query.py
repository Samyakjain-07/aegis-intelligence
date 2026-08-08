"""`POST /query`, `POST /query/followup` -- stub handlers.

Full pipeline (history-aware reformulation, multi-query expansion,
hybrid retrieval, RRF, rerank, grounded generation, numeric verification
-- `docs/architecture.md` §1 Pipeline B) is Phase 6's job. This phase
proves the request/response contract: a client (or the frontend's Chat
page) can already be built against this shape before any retrieval logic
exists.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.v1.deps import TenantContext, get_db, get_tenant_context
from src.models.schemas.query import FollowupQueryRequest, QueryRequest, QueryResponse

router = APIRouter(prefix="/query", tags=["query"])


@router.post("", response_model=QueryResponse)
def submit_query(
    body: QueryRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
) -> QueryResponse:
    """Placeholder answer: empty text, no citations, flagged low-
    confidence by construction so nothing downstream mistakes a stub
    response for a real one. Phase 6 replaces this body; the signature
    (and the DB session / tenant context already being injected) stays
    the same.
    """
    return QueryResponse(
        query_id=uuid.uuid4(),
        conversation_id=body.conversation_id or uuid.uuid4(),
        query_text=body.query_text,
        reformulated_query_text=None,
        answer_text="",
        confidence_score=0.0,
        low_confidence=True,
        citations=[],
        created_at=datetime.now(timezone.utc),
    )


@router.post("/followup", response_model=QueryResponse)
def submit_followup_query(
    body: FollowupQueryRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
) -> QueryResponse:
    """Placeholder follow-up answer -- see `submit_query`. Reformulation
    is a no-op here (`reformulated_query_text` stays `None`) until Phase
    6's `history_manager.py` exists."""
    return QueryResponse(
        query_id=uuid.uuid4(),
        conversation_id=body.conversation_id,
        query_text=body.query_text,
        reformulated_query_text=None,
        answer_text="",
        confidence_score=0.0,
        low_confidence=True,
        citations=[],
        created_at=datetime.now(timezone.utc),
    )
