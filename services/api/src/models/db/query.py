"""QUERY — one question inside a `Conversation`. Holds both the raw text
the user typed and, for follow-ups, the history-aware reformulated version
(architecture.md §1, Pipeline B step 2).

architecture.md §7: `CONVERSATION ||--o{ QUERY : contains`,
`QUERY ||--|| ANSWER : produces`, and `QUERY ||--o| EVALRESULT : scored_by`.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.db.base import Base
from src.models.db.conversation import Conversation

if TYPE_CHECKING:
    from src.models.db.answer import Answer
    from src.models.db.eval_result import EvalResult


class Query(Base):
    """One question. `reformulated_query_text` is null for a fresh
    question and populated only when Phase 6's history-aware reformulation
    rewrote a follow-up into a self-contained query.

    Table name is plural "queries", not "query" -- avoids reading oddly
    next to SQLAlchemy's own `Session.query()`/`Query` type, even though
    neither actually collides with a table name.
    """

    __tablename__ = "queries"

    query_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("conversations.conversation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    reformulated_query_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    conversation: Mapped[Conversation] = relationship(back_populates="queries")
    answer: Mapped[Answer | None] = relationship(
        back_populates="query", uselist=False, cascade="all, delete-orphan"
    )
    eval_result: Mapped[EvalResult | None] = relationship(
        back_populates="query", uselist=False, cascade="all, delete-orphan"
    )
