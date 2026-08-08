"""DOCUMENT — one ingested SEC filing, earnings-call transcript, or
investor deck.

architecture.md §7: `COMPANY ||--o{ DOCUMENT : files` and
`DOCUMENT ||--o{ DOCUMENTCHUNK : contains`.
"""
from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, String
from sqlalchemy import Enum as PgEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.db.base import Base
from src.models.db.company import Company
from src.models.db.enums import DocumentStatus, DocumentType

if TYPE_CHECKING:
    from src.models.db.document_chunk import DocumentChunk


class Document(Base):
    """A single filed document. `fiscal_quarter` is nullable because
    annual filings (10-K) and investor decks aren't always tied to one
    specific quarter the way a 10-Q is.

    `title` and `status` were both deliberately left off in Phase 2 and
    added here in Phase 4 -- see the Phase 2 decisions-log entry (the
    `status` gap) and this phase's entry (the `title` gap, found once the
    Library page actually needed a display name and the ER diagram had
    none). Both are purely additive columns on a table with no production
    data yet, which `CLAUDE.md` §4 treats as the low-risk case."""

    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "fiscal_quarter IS NULL OR fiscal_quarter BETWEEN 1 AND 4",
            name="fiscal_quarter_range",
        ),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.company_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_type: Mapped[DocumentType] = mapped_column(
        PgEnum(DocumentType, name="document_type"), nullable=False
    )
    fiscal_quarter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    upload_date: Mapped[date] = mapped_column(Date, nullable=False)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        PgEnum(DocumentStatus, name="document_status"),
        nullable=False,
        default=DocumentStatus.PENDING,
    )

    company: Mapped[Company] = relationship(back_populates="documents")
    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
