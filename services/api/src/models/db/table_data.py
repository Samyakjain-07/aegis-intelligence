"""TABLEDATA — the structured (rows/columns/headers preserved) contents of
a `chunk_type = TABLE` `DocumentChunk`. This is the direct implementation
of architecture.md §1 step 4 ("never flatten a table into prose") — a
financial table parsed as plain text loses its row/column relationships,
which is the root cause of numeric hallucination this project exists to
prevent.

architecture.md §7: `DOCUMENTCHUNK ||--o| TABLEDATA : has`.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.db.base import Base
from src.models.db.document_chunk import DocumentChunk


class TableData(Base):
    """The structured table behind one `DocumentChunk`. `chunk_id` is
    unique, not just indexed — the ER diagram's `||--o|` cardinality means
    a chunk has *at most one* table-data record, and the unique constraint
    is what actually enforces that at the database level rather than just
    by convention."""

    __tablename__ = "table_data"

    table_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("document_chunks.chunk_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    # JSONB (not JSON): Postgres stores it in a binary, indexable form and
    # supports containment/path queries later (e.g. "find tables with a
    # 'Revenue' row") without a schema migration — plain JSON only offers
    # cheaper writes, which isn't the bottleneck here since tables are
    # written once at ingestion and read many times at query time.
    raw_table_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    column_count: Mapped[int] = mapped_column(Integer, nullable=False)

    chunk: Mapped[DocumentChunk] = relationship(back_populates="table_data")
