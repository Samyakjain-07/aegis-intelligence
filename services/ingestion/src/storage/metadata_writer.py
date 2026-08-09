"""Writes relational metadata to Postgres -- `docs/architecture.md` §1
step 7's Postgres half ("richer relational metadata ... goes into the
Postgres metadata store").

Every write here is idempotent (`docs/architecture.md` §2: "re-running
ingestion on the same document should overwrite, not duplicate"), via
`INSERT ... ON CONFLICT DO UPDATE` on `document_chunks`
(document_id, page_number, chunk_index) and `table_data` (chunk_id) --
see `src/storage/models.py`'s docstring for why matching those columns is
enough without needing to know the underlying constraint's name.
`document_chunks.chunk_id` is intentionally left out of every UPDATE's
`SET` clause, so a re-ingested chunk keeps its original `chunk_id` (and
therefore its original Qdrant point ID) rather than getting a new
identity every re-run.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.storage.models import (
    ChunkType,
    Company,
    Document,
    DocumentChunk,
    DocumentStatus,
    TableData,
)


@dataclass(frozen=True, slots=True)
class DocumentContext:
    """Everything the rest of the pipeline needs to know about the
    `Document` being ingested, read once at the start of the task and
    threaded through unchanged (`tasks/ingest_document.py`)."""

    document_id: uuid.UUID
    source_url: str
    document_type: str
    fiscal_year: int
    fiscal_quarter: int | None
    ticker: str


def load_document_context(session: Session, document_id: uuid.UUID) -> DocumentContext:
    row = session.execute(
        select(Document, Company)
        .join(Company, Document.company_id == Company.company_id)
        .where(Document.document_id == document_id)
    ).first()
    if row is None:
        raise LookupError(f"Document {document_id} (or its Company) not found in Postgres.")
    document, company = row
    return DocumentContext(
        document_id=document.document_id,
        source_url=document.source_url,
        document_type=document.document_type,
        fiscal_year=document.fiscal_year,
        fiscal_quarter=document.fiscal_quarter,
        ticker=company.ticker,
    )


def set_document_status(session: Session, document_id: uuid.UUID, status: DocumentStatus) -> None:
    """A plain `UPDATE`, not an upsert -- the `Document` row always
    already exists by the time ingestion runs (`POST /documents`, Phase 4,
    is the only thing that ever creates one), so there is never a real
    conflict case to handle, and an upsert here would need to supply
    every other NOT NULL column just to satisfy a row-construction path
    that can never actually be taken.
    """
    session.execute(update(Document).where(Document.document_id == document_id).values(status=status))


def upsert_document_chunk(
    session: Session,
    *,
    document_id: uuid.UUID,
    chunk_type: ChunkType,
    content: str,
    page_number: int,
    chunk_index: int,
) -> uuid.UUID:
    """Returns the chunk's `chunk_id` -- either the freshly generated one
    (first ingestion) or the pre-existing one this (document_id,
    page_number, chunk_index) triple already had (re-ingestion). The
    caller needs this value before it can write the matching `TableData`
    row or the Qdrant point, since both are keyed by `chunk_id`.
    """
    stmt = (
        pg_insert(DocumentChunk)
        .values(
            chunk_id=uuid.uuid4(),
            document_id=document_id,
            chunk_type=chunk_type,
            content=content,
            page_number=page_number,
            chunk_index=chunk_index,
        )
        .on_conflict_do_update(
            index_elements=[
                DocumentChunk.document_id,
                DocumentChunk.page_number,
                DocumentChunk.chunk_index,
            ],
            set_={"chunk_type": chunk_type, "content": content},
        )
        .returning(DocumentChunk.chunk_id)
    )
    return session.execute(stmt).scalar_one()


def upsert_table_data(
    session: Session,
    *,
    chunk_id: uuid.UUID,
    raw_table_json: dict[str, Any],
    row_count: int,
    column_count: int,
) -> None:
    stmt = (
        pg_insert(TableData)
        .values(
            table_id=uuid.uuid4(),
            chunk_id=chunk_id,
            raw_table_json=raw_table_json,
            row_count=row_count,
            column_count=column_count,
        )
        .on_conflict_do_update(
            index_elements=[TableData.chunk_id],
            set_={
                "raw_table_json": raw_table_json,
                "row_count": row_count,
                "column_count": column_count,
            },
        )
    )
    session.execute(stmt)


def set_embedding_vector_id(session: Session, chunk_id: uuid.UUID, vector_id: str) -> None:
    session.execute(
        update(DocumentChunk).where(DocumentChunk.chunk_id == chunk_id).values(embedding_vector_id=vector_id)
    )
