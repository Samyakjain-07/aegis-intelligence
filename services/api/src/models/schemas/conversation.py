"""Pydantic response schemas for `conversations.py`.

`ConversationDetailResponse` extends `ConversationResponse` with the
conversation's `Query` rows (summarized, not each one's full `Answer` --
that level of detail belongs to `GET /query/{id}`-style access via the
query/citation routes, not a conversation listing) -- matching
`Conversation.queries`' `order_by="Query.created_at"` relationship so the
thread renders in the order questions were actually asked.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ConversationResponse(BaseModel):
    """One `Conversation` row."""

    model_config = ConfigDict(from_attributes=True)

    conversation_id: uuid.UUID
    user_id: uuid.UUID
    started_at: datetime


class QuerySummary(BaseModel):
    """A `Query` row, summarized for embedding inside a conversation
    listing -- omits `reformulated_query_text` and the full answer, which
    belong to the dedicated query/citation routes."""

    model_config = ConfigDict(from_attributes=True)

    query_id: uuid.UUID
    query_text: str
    created_at: datetime


class ConversationDetailResponse(ConversationResponse):
    """A single conversation with its queries, ordered oldest-first."""

    queries: list[QuerySummary]


class ConversationListResponse(BaseModel):
    """`GET /conversations` response envelope."""

    conversations: list[ConversationResponse]
    total: int
