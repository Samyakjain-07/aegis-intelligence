"""Shared value types for the query pipeline (`services/api/src/core/`).

Not one of the files `PROJECT_HANDBOOK.md` §6 names explicitly -- added so
`bm25_retriever.py`, `dense_retriever.py`, `rrf.py`, `hybrid_retriever.py`,
and `reranker.py` all agree on one definition of "a ranked candidate" and
"a hydrated chunk" instead of independently redefining the same shape
five times. Small and dependency-light on purpose (only the enums every
other module already needs), the same spirit as `packages/shared`'s
`SourceLocation` -- a plain value type multiple modules need to agree on,
not business logic.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from src.models.db.enums import ChunkType, DocumentType


@dataclass(frozen=True, slots=True)
class RankedChunk:
    """One retrieval candidate as a single retriever ranked it: which
    chunk, how it scored. Deliberately just an id + a score -- both
    `bm25_retriever.py` and `dense_retriever.py` produce a list of these
    *before* anything pays the cost of hydrating full chunk content from
    Postgres, since most raw candidates never survive RRF fusion into the
    much smaller set that does (see `hybrid_retriever.py`)."""

    chunk_id: uuid.UUID
    score: float


@dataclass(slots=True)
class RetrievedChunk:
    """A fully hydrated chunk -- read from Postgres exactly once, only for
    the chunk_ids that survived RRF fusion, with its `Document`/`Company`
    joined for citation display and its `TableData.raw_table_json` joined
    if it's a table chunk (needed by `numeric_verifier.py`, which must
    check claims against the *complete* table, not `content`'s truncated
    embedding-summary text -- see `numeric_verifier.py`'s docstring).

    Score fields default to `None` and are filled in by whichever stage
    actually produced them, so a chunk that makes it all the way to a
    citation carries every stage's number for observability, not just the
    last one written.
    """

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    chunk_type: ChunkType
    content: str
    page_number: int
    chunk_index: int
    ticker: str
    document_title: str
    document_type: DocumentType
    fiscal_year: int
    fiscal_quarter: int | None
    table_data: dict[str, Any] | None = None  # TableData.raw_table_json; TABLE chunks only

    bm25_score: float | None = None
    dense_score: float | None = None
    rrf_score: float | None = None
    rerank_score: float | None = None
