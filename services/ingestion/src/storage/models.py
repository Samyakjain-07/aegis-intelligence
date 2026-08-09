"""SQLAlchemy 2.0 models for the tables `services/ingestion` reads/writes:
`companies` (read-only), `documents` (read + `status` updates),
`document_chunks` and `table_data` (written by every ingestion run).

**Deliberately a second, independent set of model classes from
`services/api/src/models/db/`** -- not imports of them, not a shared
`packages/shared` module. This needs explaining, since it's the opposite
choice from `packages/shared/aegis_shared/source_location.py`:

- `PROJECT_HANDBOOK.md` §6 Phase 5's file list is scoped entirely to
  `services/ingestion/src/`; it does not mention touching
  `services/api/src/models/db/` or moving those files into
  `packages/shared`. Doing that refactor anyway would mean rewriting
  import paths across every already-migrated, already-tested file from
  Phases 2-4 (routes, `deps.py`, `alembic/env.py`, `tests/unit/`) for a
  Phase 5 task, which is a bigger, riskier change than this phase asks
  for.
- `services/api/src/infra/celery_app.py`'s own Phase 4 docstring already
  established the governing principle for this exact pair of services:
  "the two ... instances only ever agree by convention ..., never by
  sharing Python code." That was written for the Celery app, but the same
  reasoning applies to the ORM layer -- `CLAUDE.md` §1/`docs/
  architecture.md` §3 calls the two services "deliberately decoupled" so
  they can scale independently; importing `services.api.src...` from
  `services/ingestion` would silently couple their deployability (you
  could no longer ship an ingestion worker without the API's source tree
  present).
- The actual, load-bearing agreement between the two model sets is the
  **Postgres schema itself** (created once, by `services/api`'s Alembic
  migrations) -- table names, column names, and the
  `document_status`/`chunk_type` enum *type* names in Postgres. Both
  files' `__tablename__`s and `PgEnum(..., name=...)` calls point at that
  one schema; if it drifts, `alembic upgrade head` (API-side) is what
  would need to change, and both model files would need updating in
  lockstep -- a real coordination cost, accepted here as cheaper than the
  cross-service import coupling above.

Only the columns each writer actually touches are declared -- no
`relationship()`s, no back-populates, since this file only ever does
Core-style `select`/`insert ... on_conflict_do_update`/`update` statements
(`src/storage/metadata_writer.py`), never ORM graph navigation.
`create_type=False` on both `PgEnum`s is what stops SQLAlchemy from ever
trying to `CREATE TYPE` these (they already exist) -- moot today since
nothing here calls `Base.metadata.create_all()`, but explicit rather than
relying on that never happening by accident.
"""
from __future__ import annotations

import enum
import uuid
from typing import Any

from sqlalchemy import Enum as PgEnum
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class DocumentStatus(str, enum.Enum):
    """Mirrors `services/api/src/models/db/enums.py::DocumentStatus`
    value-for-value -- ingestion only ever writes `PROCESSING`,
    `COMPLETED`, and `FAILED` (never `PENDING`, which `POST /documents`
    already sets), but all four are declared for a complete, honest
    mapping to the Postgres `document_status` enum type."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ChunkType(str, enum.Enum):
    """Mirrors `services/api/src/models/db/enums.py::ChunkType`
    value-for-value -- maps to Postgres's `chunk_type` enum type."""

    NARRATIVE = "narrative"
    TABLE = "table"
    FOOTNOTE = "footnote"


class IngestionBase(DeclarativeBase):
    """A separate `DeclarativeBase` from `services/api`'s
    `src.models.db.base.Base` -- see this module's docstring for why. No
    shared `MetaData`/naming convention is needed here since nothing in
    this file ever generates DDL or an Alembic migration; that remains
    exclusively `services/api`'s responsibility."""


class Company(IngestionBase):
    """Read-only here -- ingestion never creates or updates a `Company`
    row (that's `POST /documents`'s job, Phase 4); only reads `ticker` for
    Qdrant payload metadata (`src/storage/qdrant_writer.py`)."""

    __tablename__ = "companies"

    company_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    ticker: Mapped[str] = mapped_column(String(10))
    name: Mapped[str] = mapped_column(String(255))
    sector: Mapped[str] = mapped_column(String(100))


class Document(IngestionBase):
    """Read at task start (`source_url`, `document_type`, fiscal fields)
    and status-updated at each pipeline transition
    (`src/storage/metadata_writer.py::set_document_status`).
    `document_type` is mapped as a plain `String`, not `PgEnum`+the API's
    `DocumentType` -- ingestion only ever reads this column, and a plain
    string read is simpler than importing/mirroring a third enum for a
    value this file never writes."""

    __tablename__ = "documents"

    document_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("companies.company_id")
    )
    document_type: Mapped[str] = mapped_column(String)
    fiscal_quarter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fiscal_year: Mapped[int] = mapped_column(Integer)
    source_url: Mapped[str] = mapped_column(String(2048))
    title: Mapped[str] = mapped_column(String(512))
    status: Mapped[DocumentStatus] = mapped_column(
        PgEnum(DocumentStatus, name="document_status", create_type=False)
    )


class DocumentChunk(IngestionBase):
    """Written once per chunk via
    `src/storage/metadata_writer.py::upsert_document_chunk` -- an
    `INSERT ... ON CONFLICT (document_id, page_number, chunk_index)
    DO UPDATE`, which is what makes re-running ingestion on the same
    document idempotent (`docs/architecture.md` §2) without needing this
    file to know the unique constraint's *name*, only the three columns it
    covers (Postgres resolves an `ON CONFLICT (col, col, col)` target by
    matching columns against any real unique constraint/index, regardless
    of what it's named)."""

    __tablename__ = "document_chunks"

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("documents.document_id")
    )
    chunk_type: Mapped[ChunkType] = mapped_column(
        PgEnum(ChunkType, name="chunk_type", create_type=False)
    )
    content: Mapped[str] = mapped_column(Text)
    page_number: Mapped[int] = mapped_column(Integer)
    chunk_index: Mapped[int] = mapped_column(Integer)
    embedding_vector_id: Mapped[str | None] = mapped_column(String(255), nullable=True)


class TableData(IngestionBase):
    """Written once per table chunk via
    `src/storage/metadata_writer.py::upsert_table_data` (only for
    `chunk_type == TABLE` chunks). `raw_table_json` stores the structured
    `{"headers": [...], "rows": [[...], ...]}` shape produced by
    `src/parsing/table_extractor.py` -- never a flattened string, matching
    `services/api`'s own `TableData.raw_table_json` column exactly."""

    __tablename__ = "table_data"

    table_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("document_chunks.chunk_id")
    )
    raw_table_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    row_count: Mapped[int] = mapped_column(Integer)
    column_count: Mapped[int] = mapped_column(Integer)
