"""USER — a named person inside an `Organization`, either an analyst or an
admin (see `enums.UserRole`).

architecture.md §7: `ORGANIZATION ||--o{ USER : employs` and
`USER ||--o{ CONVERSATION : starts`.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum as PgEnum
from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.db.base import Base
from src.models.db.enums import UserRole
from src.models.db.organization import Organization

if TYPE_CHECKING:
    # Conversation is built after User in the fixed order (CLAUDE.md §3),
    # so only import it for typing here to keep the import graph acyclic —
    # conversation.py does the normal runtime import of User instead.
    from src.models.db.conversation import Conversation


class User(Base):
    """A person who can start conversations and ask questions. Scoped to
    exactly one `Organization`."""

    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.org_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # 320 = RFC 5321's theoretical max (64 local-part + '@' + 255 domain).
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    role: Mapped[UserRole] = mapped_column(
        PgEnum(UserRole, name="user_role"), nullable=False, default=UserRole.ANALYST
    )

    organization: Mapped[Organization] = relationship(back_populates="users")
    conversations: Mapped[list[Conversation]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
