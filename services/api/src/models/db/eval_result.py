"""EVALRESULT — the eval-harness score for one `Query`, produced by
Phase 8's RAGAS/DeepEval runner rather than at query time. This is what
turns "retrieval seems good" into the CI-gated number `PROJECT_HANDBOOK.md`
§8 asks for on every change.

architecture.md §7: `QUERY ||--o| EVALRESULT : scored_by`.
"""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, CheckConstraint, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.db.base import Base
from src.models.db.query import Query


class EvalResult(Base):
    """At most one per `Query` (only present once the eval suite has run
    against it — most `Query` rows in normal usage will never get one;
    this table is populated by the offline eval harness, not the live
    query pipeline)."""

    __tablename__ = "eval_results"
    __table_args__ = (
        CheckConstraint(
            "retrieval_precision >= 0 AND retrieval_precision <= 1",
            name="retrieval_precision_range",
        ),
        CheckConstraint(
            "groundedness_score >= 0 AND groundedness_score <= 1",
            name="groundedness_score_range",
        ),
    )

    eval_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    query_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("queries.query_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    retrieval_precision: Mapped[float] = mapped_column(Float, nullable=False)
    groundedness_score: Mapped[float] = mapped_column(Float, nullable=False)
    flagged_by_human: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    query: Mapped[Query] = relationship(back_populates="eval_result")
