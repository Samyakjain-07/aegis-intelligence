"""Finds the same line-item ("metric") across every ingested filing for a
company -- the read path behind `GET /compare/metric`
(`docs/architecture.md` §8 UC5, "Compare metrics across quarters").

Row-label substring matching against `TableData.raw_table_json`, not an
LLM/embedding lookup: a real financial table's row already carries the
metric name as its first cell (e.g. "Revenue", "Net income") by
construction of `table_extractor.py`'s never-flatten extraction, so a
plain case-insensitive substring match is enough to find it. Deliberately
has no LLM call in it anywhere, same reasoning as `numeric_verifier.py`:
"does this row look like the metric?" is answerable from the row's own
label text, not something worth trading for LLM-shaped risk. See
`docs/DECISIONS_LOG.md` for the ranked-match alternative considered and
deferred (no gold set exists yet to validate a smarter match against).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from src.core.citation_resolver import resolve_source_location
from src.core.types import RetrievedChunk
from src.models.db.company import Company
from src.models.db.document import Document
from src.models.db.document_chunk import DocumentChunk
from src.models.db.enums import ChunkType, DocumentStatus


@dataclass(frozen=True, slots=True)
class MetricMatch:
    """One matched table row, plus enough of its parent `Document` for
    `api/v1/routes/compare.py` to label it by fiscal period."""

    document: Document
    page_number: int
    matched_row_label: str
    headers: list[str]
    values: list[str]
    exact_location: str


def _row_label_matches(metric_query: str, row: list[Any]) -> bool:
    if not row:
        return False
    label = str(row[0]).strip()
    return bool(label) and metric_query.lower() in label.lower()


def _to_retrieved_chunk(chunk: DocumentChunk, document: Document, ticker: str) -> RetrievedChunk:
    """Just enough of `RetrievedChunk`'s shape for
    `citation_resolver.resolve_source_location` to resolve a real
    `exact_location` (including, for a table chunk, the Qdrant-only
    `table_cell_ref` -- see that module's docstring for why it isn't in
    Postgres). Score fields stay at their `None` defaults: nothing here
    ever ranked this chunk against anything, it was found by a direct
    row-label match."""
    return RetrievedChunk(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        chunk_type=chunk.chunk_type,
        content=chunk.content,
        page_number=chunk.page_number,
        chunk_index=chunk.chunk_index,
        ticker=ticker,
        document_title=document.title,
        document_type=document.document_type,
        fiscal_year=document.fiscal_year,
        fiscal_quarter=document.fiscal_quarter,
        table_data=chunk.table_data.raw_table_json if chunk.table_data is not None else None,
    )


def find_metric_across_documents(
    db: Session, ticker: str, metric_query: str
) -> tuple[Company | None, list[MetricMatch]]:
    """Returns `(None, [])` if no `Company` matches `ticker`. Otherwise
    walks every `COMPLETED` document for that company -- oldest fiscal
    year/quarter first, annual (`fiscal_quarter IS NULL`) filings sorting
    before same-year quarters -- and returns at most one match per
    document: the *first* table row (by page number, then chunk order,
    then row order within the table) whose first cell contains
    `metric_query` as a case-insensitive substring. A document with no
    matching row is simply absent from the result, not returned as a
    null/empty entry -- the Compare page only has something to plot for
    periods where the metric was actually found.

    "First match wins," not "best match": a filing's primary income
    statement table almost always appears before segment/footnote detail
    tables that might reuse the same line-item label, so first-match
    already picks the right section in the common case. A ranked/
    disambiguated match is a reasonable improvement once Phase 8's gold
    set exists to validate it against -- not something to guess at
    without one.
    """
    normalized_ticker = ticker.strip().upper()
    company = db.execute(select(Company).where(Company.ticker == normalized_ticker)).scalar_one_or_none()
    if company is None:
        return None, []

    documents = (
        db.execute(
            select(Document)
            .where(Document.company_id == company.company_id)
            .where(Document.status == DocumentStatus.COMPLETED)
            .options(
                joinedload(
                    Document.chunks.and_(DocumentChunk.chunk_type == ChunkType.TABLE)
                ).joinedload(DocumentChunk.table_data)
            )
            .order_by(Document.fiscal_year.asc(), Document.fiscal_quarter.asc().nulls_first())
        )
        .unique()
        .scalars()
        .all()
    )

    matches: list[MetricMatch] = []
    for document in documents:
        table_chunks = sorted(
            (
                chunk
                for chunk in document.chunks
                if chunk.chunk_type == ChunkType.TABLE and chunk.table_data is not None
            ),
            key=lambda chunk: (chunk.page_number, chunk.chunk_index),
        )
        for chunk in table_chunks:
            table_data = chunk.table_data
            if table_data is None:
                continue  # unreachable given the filter above; narrows the type for mypy
            raw = table_data.raw_table_json
            rows = raw.get("rows", [])
            matched_row = next((row for row in rows if _row_label_matches(metric_query, row)), None)
            if matched_row is None:
                continue
            retrieved = _to_retrieved_chunk(chunk, document, company.ticker)
            matches.append(
                MetricMatch(
                    document=document,
                    page_number=chunk.page_number,
                    matched_row_label=str(matched_row[0]).strip(),
                    headers=[str(h) for h in raw.get("headers", [])],
                    values=[str(cell) for cell in matched_row],
                    exact_location=resolve_source_location(retrieved).exact_location(),
                )
            )
            break  # first matching row in this document wins -- see docstring

    return company, matches
