"""CITATION — one piece of evidence backing an `Answer`, pointing at the
exact `DocumentChunk` (and, within it, `exact_location`) it was drawn from.
This is the object that makes the `source_location` concept
(architecture.md §2/§3) visible to the end user.

architecture.md §7: `ANSWER ||--o{ CITATION : cites` and
`DOCUMENTCHUNK ||--o{ CITATION : referenced_by`.
"""
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.db.answer import Answer
from src.models.db.base import Base
from src.models.db.document_chunk import DocumentChunk


class Citation(Base):
    """One evidence pointer. `snippet` and `exact_location` are stored
    directly on this row (not looked up live from the chunk each time) so
    a citation remains a self-contained, truthful record of what was shown
    to the user even if the underlying chunk is later changed."""

    __tablename__ = "citations"

    citation_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    answer_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("answers.answer_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Deliberately no ondelete="CASCADE" here (Postgres default is
    # NO ACTION / RESTRICT) -- see the decisions-log entry for this file.
    # A chunk that has ever been cited cannot be silently hard-deleted out
    # from under an existing citation; whatever re-ingestion logic deletes
    # old chunks (Phase 5) has to reckon with that on purpose.
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("document_chunks.chunk_id"),
        nullable=False,
        index=True,
    )
    exact_location: Mapped[str] = mapped_column(String(255), nullable=False)
    snippet: Mapped[str] = mapped_column(Text, nullable=False)

    answer: Mapped[Answer] = relationship(back_populates="citations")
    chunk: Mapped[DocumentChunk] = relationship(back_populates="citations")
