"""Import hub for all SQLAlchemy models.

Every model must be imported at least once, before any mapper is
configured -- Alembic's `env.py` imports `Base.metadata` via this package
as `target_metadata` for autogenerate, and SQLAlchemy's declarative
registry needs every class that appears in a `TYPE_CHECKING`-only
relationship type hint (e.g. `Organization.users: Mapped[list["User"]]`)
to have actually been defined somewhere before that string gets resolved.
Importing only a subset here would make autogenerate silently see only a
subset of tables.

The imports below are alphabetized (ruff/isort), not listed in
`CLAUDE.md` §3's fixed build order -- that order constrains which module
is allowed to import which other module *at definition time* (see the
`TYPE_CHECKING` vs. normal-import split explained in each model file), not
the order names are re-exported from this hub. SQLAlchemy resolves
`TYPE_CHECKING`-only forward references via its class registry (matching
on class name) once every module here has executed at least once, so the
textual order of the lines below doesn't matter, only that all 11 are
present.
"""
from __future__ import annotations

from src.models.db.answer import Answer
from src.models.db.base import Base
from src.models.db.citation import Citation
from src.models.db.company import Company
from src.models.db.conversation import Conversation
from src.models.db.document import Document
from src.models.db.document_chunk import DocumentChunk
from src.models.db.enums import ChunkType, DocumentType, OrgTier, UserRole
from src.models.db.eval_result import EvalResult
from src.models.db.organization import Organization
from src.models.db.query import Query
from src.models.db.table_data import TableData
from src.models.db.user import User

__all__ = [
    "Answer",
    "Base",
    "ChunkType",
    "Citation",
    "Company",
    "Conversation",
    "Document",
    "DocumentChunk",
    "DocumentType",
    "EvalResult",
    "OrgTier",
    "Organization",
    "Query",
    "TableData",
    "User",
    "UserRole",
]
