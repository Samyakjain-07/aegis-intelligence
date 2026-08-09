"""add document chunks content fts index

Revision ID: 3100d4408cc5
Revises: 8c520544e49c
Create Date: 2026-08-09 13:00:33.424953

Phase 6 (`core/bm25_retriever.py`): a GIN index over
`to_tsvector('english', content)` so Postgres full-text search
(`ts_rank_cd`/`plainto_tsquery`) -- this project's sparse-retrieval half
of hybrid search, see that module's docstring for why Postgres FTS was
chosen over a new search-engine dependency -- doesn't do a sequential
`to_tsvector` scan over every row on every query. Hand-written, not
autogenerate output: SQLAlchemy's `Column`/`Index` model has no built-in
expression-index construct that maps onto `CREATE INDEX ... USING GIN
(to_tsvector(...))`, so autogenerate has nothing to diff against here (the
underlying `documents_chunks.content` column itself is unchanged) -- same
"hand-adjust past what autogenerate can express" situation as
`8c520544e49c`'s enum-creation call, for a different underlying reason.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '3100d4408cc5'
down_revision: Union[str, Sequence[str], None] = '8c520544e49c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEX_NAME = "ix_document_chunks_content_fts"


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        f"CREATE INDEX {_INDEX_NAME} ON document_chunks "
        "USING GIN (to_tsvector('english', content))"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(f"DROP INDEX {_INDEX_NAME}")
