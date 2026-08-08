"""Python enums backing Postgres-native ENUM columns.

Using `enum.Enum` (mapped via SQLAlchemy's `Enum` type in each model) rather
than a plain `String` with app-level validation means an invalid value is
rejected by the database itself -- a bad write from a bug, a manual `psql`
edit, or a future service that forgets the app-layer check all get caught
the same way. The tradeoff is schema migrations are required to add a new
value (Postgres ENUM types aren't append-only without an `ALTER TYPE`), which
is acceptable here since these four value sets are domain concepts (SEC
filing types, chunk categories, the two human actors, subscription tiers),
not something expected to grow often.

Each enum subclasses `str` as well as `enum.Enum` so values serialize
directly as their string value in Pydantic schemas/JSON responses in later
phases, without a separate `.value` lookup at every call site.
"""
from __future__ import annotations

import enum


class DocumentType(str, enum.Enum):
    """Matches the document categories from architecture.md §1 step 2
    (classify document type) and §7's `DOCUMENT.document_type`. 10-K and
    10-Q are broken out as separate values rather than one generic "filing"
    because they need different section-parsing rules downstream (a 10-Q
    has no full risk-factors section refresh, for instance)."""

    FORM_10K = "form_10k"
    FORM_10Q = "form_10q"
    EARNINGS_TRANSCRIPT = "earnings_transcript"
    INVESTOR_DECK = "investor_deck"


class ChunkType(str, enum.Enum):
    """Matches the three-way split from architecture.md §1 step 3
    (layout-aware parsing splits narrative text, tables, and footnotes
    apart) and step 4-5 (tables extracted structured, narrative chunked
    separately). A `DocumentChunk` with `chunk_type = TABLE` is the one
    that gets a companion `TableData` row; `NARRATIVE`/`FOOTNOTE` chunks
    never do -- see `document_chunk.py`/`table_data.py`."""

    NARRATIVE = "narrative"
    TABLE = "table"
    FOOTNOTE = "footnote"


class UserRole(str, enum.Enum):
    """Matches the two human actors in architecture.md §8's use-case
    diagrams (Analyst, Admin). The "Scheduler" actor there is a system/cron
    actor that triggers re-ingestion jobs, not a person with a `User` row,
    so it has no corresponding value here."""

    ANALYST = "analyst"
    ADMIN = "admin"


class DocumentStatus(str, enum.Enum):
    """Lifecycle status of a `Document` row, from upload through ingestion.

    Added in Phase 4 (`PROJECT_HANDBOOK.md`), not Phase 2 -- flagged as a
    real gap in `document.py`'s Phase 2 decisions-log entry:
    `architecture.md` §1 step 1 describes ingestion creating a `Document`
    with status `pending`, but the pasted §7 ER diagram's `DOCUMENT` entity
    has no `status` field at all. `PROCESSING`/`FAILED` go beyond what
    Phase 4 strictly needs (`POST /documents` only ever writes `PENDING`)
    but are added now rather than in two more piecemeal migrations later --
    Phase 5's real Celery task is the only thing that will ever transition
    a row through the other three values, and the Library page's status
    badge needs to render `PROCESSING`/`FAILED` distinctly from `PENDING`
    once that exists."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class OrgTier(str, enum.Enum):
    """Subscription tier for an `Organization`. architecture.md §7 only
    specifies `ORGANIZATION.tier: string` without enumerating values --
    this is the standard three-tier SaaS convention, kept deliberately
    simple until real pricing/entitlements are designed."""

    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"
