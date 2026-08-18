"""Pydantic response schemas for `admin.py`.

Backs three of `docs/architecture.md` §8's Admin use cases directly ("View
analytics dashboard" -- KPI cards + the query-volume chart -- and "Review
flagged answers"); "Manage org users" and "Configure retention & access"
aren't wired to a route yet -- out of scope for this phase's surface, left
for whichever later phase actually implements org/user management.

Phase 7 (`PROJECT_HANDBOOK.md`): every field below is now computed from
real `Document`/`Conversation`/`Query`/`Answer`/`Citation`/`EvalResult`
rows in `api/v1/routes/admin.py` -- see that module's docstring for the
tenant-scoping rule (query/conversation/answer data is scoped by
`tenant.org_id`; `Document`/`Company` counts are not, matching
`documents.py`'s Phase 4 precedent that the filing corpus is shared
reference data, not tenant-owned).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class QueryVolumeDayResponse(BaseModel):
    """One day of the admin dashboard's query-volume-vs-flagged-responses
    chart -- real `Query`/`Answer`/`EvalResult` counts grouped by day,
    replacing the frontend's `MOCK_CHART_DATA`."""

    date: str  # ISO date (YYYY-MM-DD), UTC
    query_count: int
    flagged_count: int


class TickerCitationCountResponse(BaseModel):
    """One row of the "most-cited companies" panel. Replaces the Admin
    page's static "Top Query Topics" mock -- topic modeling would need a
    new dependency (an embedding-clustering library, or an LLM call) not
    already in the agreed stack (`CLAUDE.md` §3); which company's filings
    actually got cited across real answers is meaningful, queryable data
    the schema already supports without one. See
    `docs/DECISIONS_LOG.md`."""

    ticker: str
    citation_count: int
    # 0..100, relative to the busiest ticker in this result set -- the
    # frontend's progress-bar width binds directly to this instead of
    # recomputing a max client-side.
    percent_of_max: float


class AdminAnalyticsResponse(BaseModel):
    """KPI cards + query-volume-chart data for the admin dashboard."""

    total_documents: int
    indexed_document_count: int
    total_conversations: int
    total_queries: int
    average_confidence_score: float | None
    flagged_answer_count: int
    # flagged_answer_count / total_queries, 0..1 -- what the "Low
    # Confidence Rate" KPI card renders as a percentage. `None` (not 0)
    # when total_queries is 0 -- a rate of 0% and "no data yet" are
    # different facts the UI should be able to tell apart.
    low_confidence_rate: float | None
    active_analyst_count: int
    query_volume_last_7_days: list[QueryVolumeDayResponse]
    top_cited_tickers: list[TickerCitationCountResponse]


class FlaggedAnswerResponse(BaseModel):
    """One row in the flagged-answers review table -- an `Answer` that
    either fell below the live confidence threshold at generation time
    (`core.confidence_scorer.LOW_CONFIDENCE_THRESHOLD`) or was flagged by
    a human reviewer via `EvalResult.flagged_by_human` (populated by
    Phase 8's eval harness, not yet built -- so today every flagged row
    reaches this table via the confidence path; the human-review path
    exists in the query/filter logic regardless, so nothing has to change
    once Phase 8 starts writing `EvalResult` rows)."""

    model_config = ConfigDict(from_attributes=True)

    answer_id: uuid.UUID
    query_id: uuid.UUID
    conversation_id: uuid.UUID
    user_email: str
    query_text: str
    answer_text: str
    confidence_score: float
    flag_reason: str
    generated_at: datetime


class FlaggedAnswersListResponse(BaseModel):
    """`GET /admin/flagged-answers` response envelope. `total` is the full
    matching count, independent of `limit` -- mirrors
    `DocumentListResponse`'s already-established total-vs-page-size
    contract."""

    flagged_answers: list[FlaggedAnswerResponse]
    total: int
