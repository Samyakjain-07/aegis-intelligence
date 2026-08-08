"""DOCUMENTCHUNK — one narrative, table, or footnote unit produced by
ingestion. Carries the `source_location` pieces (`page_number` +
`chunk_index`, plus the FK back to `document_id`) that every citation in
the system ultimately points to.

architecture.md §7: `DOCUMENT ||--o{ DOCUMENTCHUNK : contains`,
`DOCUMENTCHUNK ||--o| TABLEDATA : has`, and
`DOCUMENTCHUNK ||--o{ CITATION : referenced_by`.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum as PgEnum
from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.db.base import Base
from src.models.db.document import Document
from src.models.db.enums import ChunkType

if TYPE_CHECKING:
    from src.models.db.citation import Citation
    from src.models.db.table_data import TableData


class DocumentChunk(Base):
    """A retrievable unit of a `Document`. `chunk_type = TABLE` chunks get
    a companion `TableData` row holding the structured (never flattened)
    table; `NARRATIVE`/`FOOTNOTE` chunks don't."""

    __tablename__ = "document_chunks"
    __table_args__ = (
        # Ordinal identity for a chunk within its document/page — see the
        # decisions-log entry for why this is added beyond the pasted ER
        # diagram's column list. Also the mechanism that makes re-running
        # ingestion on the same document idempotent (architecture.md §2):
        # upserting on this key overwrites instead of duplicating.
        UniqueConstraint(
            "document_id",
            "page_number",
            "chunk_index",
            name="uq_document_chunks_document_id_page_number_chunk_index",
        ),
    )

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.document_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_type: Mapped[ChunkType] = mapped_column(
        PgEnum(ChunkType, name="chunk_type"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    # Ordinal position of this chunk among all chunks on the same page —
    # see the UniqueConstraint above.
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # The Qdrant point ID this chunk's embedding was written to. Nullable
    # because the row is written to Postgres slightly before/independently
    # of the Qdrant upsert completing in Phase 5's ingestion task; unique
    # once populated, since each chunk embeds to exactly one vector point.
    embedding_vector_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True
    )

    document: Mapped[Document] = relationship(back_populates="chunks")
    table_data: Mapped[TableData | None] = relationship(
        back_populates="chunk", uselist=False, cascade="all, delete-orphan"
    )
    citations: Mapped[list[Citation]] = relationship(back_populates="chunk")
