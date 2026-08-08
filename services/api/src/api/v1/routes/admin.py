"""`GET /admin/analytics`, `GET /admin/flagged-answers` -- stub handlers
backing two of `docs/architecture.md` §8's Admin use cases ("View
analytics dashboard", "Review flagged answers"). "Manage org users" and
"Configure retention & access" have no route yet -- out of scope for this
phase's surface, left for whichever later phase implements org/user
management.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.v1.deps import TenantContext, get_db, get_tenant_context
from src.models.schemas.admin import AdminAnalyticsResponse, FlaggedAnswersListResponse

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/analytics", response_model=AdminAnalyticsResponse)
def get_analytics(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
) -> AdminAnalyticsResponse:
    """Placeholder all-zero KPIs. Phase 7 aggregates real `Document`/
    `Conversation`/`Query`/`Answer` counts, scoped by `tenant.org_id`.
    Real role-based authorization (admin-only) isn't enforced yet either
    -- `tenant.role` is always `None` until real auth exists (see
    `deps.py`), so there's nothing meaningful to check against yet.
    """
    return AdminAnalyticsResponse(
        total_documents=0,
        total_conversations=0,
        total_queries=0,
        average_confidence_score=None,
        flagged_answer_count=0,
    )


@router.get("/flagged-answers", response_model=FlaggedAnswersListResponse)
def list_flagged_answers(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
) -> FlaggedAnswersListResponse:
    """Placeholder empty list. Phase 7 queries `Answer` rows either below
    the confidence threshold or with a linked `EvalResult.flagged_by_human
    = True`, scoped by `tenant.org_id`."""
    return FlaggedAnswersListResponse(flagged_answers=[], total=0)
