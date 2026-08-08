"""`GET /conversations`, `GET /conversations/{conversation_id}` -- stub
handlers backing the conversation-history browsing part of
`docs/architecture.md` §8's "View answer with citations" use case.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.v1.deps import TenantContext, get_db, get_tenant_context
from src.models.schemas.conversation import (
    ConversationDetailResponse,
    ConversationListResponse,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=ConversationListResponse)
def list_conversations(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
) -> ConversationListResponse:
    """Placeholder empty list. A later phase queries `Conversation` rows
    scoped by `tenant.user_id`, ordered most-recent-first."""
    return ConversationListResponse(conversations=[], total=0)


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
def get_conversation(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
) -> ConversationDetailResponse:
    """Placeholder detail -- echoes the requested ID back with no queries.
    A later phase 404s when the conversation doesn't exist or isn't owned
    by the requesting tenant; this stub always succeeds instead, since
    there's no real ownership check to enforce yet.
    """
    return ConversationDetailResponse(
        conversation_id=conversation_id,
        user_id=tenant.user_id or uuid.uuid4(),
        started_at=datetime.now(timezone.utc),
        queries=[],
    )
