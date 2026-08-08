"""ANSWER — the generated response to one `Query`, including its
confidence score (architecture.md §1, Pipeline B steps 9-11).

architecture.md §7: `QUERY ||--|| ANSWER : produces` and
`ANSWER ||--o{ CITATION : cites`.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.db.base import Base
from src.models.db.query import Query

if TYPE_CHECKING:
    from src.models.db.citation import Citation


class Answer(Base):
    """The one generated answer for a `Query`. `confidence_score` reflects
    both the rerank confidence check and, if numeric claims were present,
    whether they verified against source (architecture.md §3's decision
    table) — it's a single collapsed signal, not two separate scores."""

    __tablename__ = "answers"
    __table_args__ = (
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name="confidence_score_range",
        ),
    )

    answer_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    query_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("queries.query_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    query: Mapped[Query] = relationship(back_populates="answer")
    citations: Mapped[list[Citation]] = relationship(
        back_populates="answer", cascade="all, delete-orphan"
    )
