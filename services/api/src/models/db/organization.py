"""ORGANIZATION — top of the multi-tenancy hierarchy.

architecture.md §7: `ORGANIZATION ||--o{ USER : employs`. Every `User`
belongs to exactly one organization; every tenant-scoped query built in
Phase 3+ filters through a user's `org_id`.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum as PgEnum
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.db.base import Base
from src.models.db.enums import OrgTier

if TYPE_CHECKING:
    # Import-only-for-typing to avoid a circular import: user.py needs a
    # normal runtime import of Organization (it's built after this file),
    # but Organization only ever needs User as a type hint on the "many"
    # side of the relationship, never at runtime.
    from src.models.db.user import User


class Organization(Base):
    """A tenant. Owns a set of `User`s and (indirectly, via those users'
    conversations) all of Aegis's usage data."""

    __tablename__ = "organizations"

    org_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    tier: Mapped[OrgTier] = mapped_column(
        PgEnum(OrgTier, name="org_tier"), nullable=False, default=OrgTier.FREE
    )

    users: Mapped[list[User]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
