"""Pydantic response schemas for `admin.py`.

Backs two of `docs/architecture.md` §8's Admin use cases directly ("View
analytics dashboard", "Review flagged answers"); "Manage org users" and
"Configure retention & access" aren't wired to a route yet -- out of scope
for this phase's stub surface, left for whichever later phase actually
implements org/user management.
"""
from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class AdminAnalyticsResponse(BaseModel):
    """KPI cards + revenue-over-time-chart-adjacent counters for the admin
    dashboard. All placeholder zeros in this phase -- Phase 7 computes
    these from real `Document`/`Query`/`Answer` rows."""

    total_documents: int
    total_conversations: int
    total_queries: int
    average_confidence_score: float | None
    flagged_answer_count: int


class FlaggedAnswerResponse(BaseModel):
    """One row in the flagged-answers review table -- an `Answer` that
    either fell below the confidence threshold at generation time or was
    flagged by a human reviewer (architecture.md §8's "Review flagged
    answers" use case)."""

    model_config = ConfigDict(from_attributes=True)

    answer_id: uuid.UUID
    query_id: uuid.UUID
    query_text: str
    answer_text: str
    confidence_score: float


class FlaggedAnswersListResponse(BaseModel):
    """`GET /admin/flagged-answers` response envelope."""

    flagged_answers: list[FlaggedAnswerResponse]
    total: int
