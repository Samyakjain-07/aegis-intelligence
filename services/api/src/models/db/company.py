"""COMPANY — the SEC filer a `Document` belongs to.

architecture.md §7: `COMPANY ||--o{ DOCUMENT : files`.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.db.base import Base

if TYPE_CHECKING:
    from src.models.db.document import Document


class Company(Base):
    """A publicly-traded company (e.g. AAPL, NVDA) that files the documents
    ingested into Aegis. Reference data — created once per ticker, rarely
    updated."""

    __tablename__ = "companies"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sector: Mapped[str] = mapped_column(String(100), nullable=False)

    documents: Mapped[list[Document]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
