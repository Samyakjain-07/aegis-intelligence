"""Pydantic request/response schemas for `POST /query` and
`POST /query/followup`.

`QueryResponse` doesn't mirror a single ORM model 1:1 the way
`DocumentResponse`/`CitationResponse` do -- it's the composed shape Phase
6's query pipeline (`docs/architecture.md` §1 Pipeline B, steps 1-11)
produces by joining a `Query`, its `Answer`, and the `Answer`'s
`Citation`s into one response. `low_confidence` isn't a database column;
it's the response-shape home for architecture.md §3's decision point
("retrieval confidence above threshold? ... tag the response as
low-confidence so the UI can surface a warning") -- named to be distinct
from `EvalResult.flagged_by_human`, which is a human reviewer's judgment
made later in Phase 8, not a runtime confidence gate.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.models.schemas.citation import CitationResponse


class QueryRequest(BaseModel):
    """A fresh question. `conversation_id` is optional -- omitting it
    starts a new conversation (Phase 6 creates one); passing it attaches
    the question to an existing thread without invoking follow-up
    reformulation."""

    conversation_id: uuid.UUID | None = None
    query_text: str = Field(..., min_length=1)


class FollowupQueryRequest(BaseModel):
    """A follow-up question. `conversation_id` is required -- history-aware
    reformulation (architecture.md §1 Pipeline B step 2) needs the prior
    turns of a specific conversation to rewrite this into a self-contained
    query."""

    conversation_id: uuid.UUID
    query_text: str = Field(..., min_length=1)


class QueryResponse(BaseModel):
    """The full answer to one question: the (possibly reformulated) query,
    the generated answer, its confidence signal, and the citations backing
    it. Placeholder/empty in this phase -- Phase 6 populates it for real."""

    model_config = ConfigDict(from_attributes=True)

    query_id: uuid.UUID
    conversation_id: uuid.UUID
    query_text: str
    reformulated_query_text: str | None
    answer_text: str
    confidence_score: float
    low_confidence: bool
    citations: list[CitationResponse]
    created_at: datetime
