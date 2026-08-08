"""CONVERSATION — a chat thread started by a `User`. Groups the `Query`
rows that make up history-aware follow-up reformulation (architecture.md
§1, Pipeline B step 2).

architecture.md §7: `USER ||--o{ CONVERSATION : starts` and
`CONVERSATION ||--o{ QUERY : contains`.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.db.base import Base
from src.models.db.user import User

if TYPE_CHECKING:
    from src.models.db.query import Query


class Conversation(Base):
    """One chat thread. `queries` is ordered by `created_at` so history-
    aware reformulation in Phase 6 can walk it in the order questions were
    actually asked."""

    __tablename__ = "conversations"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    user: Mapped[User] = relationship(back_populates="conversations")
    queries: Mapped[list[Query]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Query.created_at",
    )
