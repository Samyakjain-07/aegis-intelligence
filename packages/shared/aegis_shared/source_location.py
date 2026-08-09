"""SourceLocation — the identifier every retrievable chunk carries from the
moment ingestion creates it, through Qdrant and Postgres, all the way to a
citation object in a future query response.

`docs/architecture.md` §2 names this the single most important design
decision in the ingestion pipeline: "every chunk written during ingestion
carries a `source_location` ... created once, at ingestion time, and
travels unchanged ... into the final citation object -- it is never
regenerated or re-derived." Living in `packages/shared` (not
`services/ingestion` or `services/api`) is what makes "unchanged" a fact
about the code rather than a convention two independently-maintained
copies have to keep agreeing on by hand -- ingestion constructs one
instance per chunk while writing it (Phase 5, this package's first
consumer); Phase 6's `citation_resolver.py` (`services/api`) will import
this exact same class to read one back out of Qdrant's payload and build a
`Citation.exact_location`.

Dependency-free on purpose: no SQLAlchemy, no service-specific imports.
`services/ingestion/src/storage/models.py` deliberately does *not* live
here (see that file's docstring) -- ORM models are heavyweight and
service-specific in how they're used, whereas this is a plain value object
both services only need to agree on the *shape* of.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Literal

ChunkKind = Literal["narrative", "table", "footnote"]


@dataclass(frozen=True, slots=True)
class SourceLocation:
    """`document_id` + `page_number` are the two coordinates every chunk
    has. `table_cell_ref` is required for `chunk_type == "table"` chunks
    (which table on the page, e.g. `"table 0"` -- see
    `services/ingestion/src/chunking/table_chunker.py`) and unused
    otherwise; narrative/footnote chunks instead expose `text_span`,
    derived from `chunk_index` (see that property's docstring for the
    tradeoff of not tracking exact character offsets yet).
    """

    document_id: uuid.UUID
    page_number: int
    chunk_type: ChunkKind
    chunk_index: int
    table_cell_ref: str | None = None

    def __post_init__(self) -> None:
        if self.chunk_type == "table" and self.table_cell_ref is None:
            raise ValueError("table_cell_ref is required when chunk_type == 'table'.")

    @property
    def text_span(self) -> str | None:
        """Chunk-ordinal pointer for narrative/footnote chunks, e.g.
        `"chunk 2"`. Not populated for table chunks (`table_cell_ref` is
        the pointer there instead). This is ordinal, not a character-offset
        span -- exact offsets aren't tracked by `agentic_chunker.py` today;
        see `docs/DECISIONS_LOG.md`'s tradeoffs note for this file."""
        if self.chunk_type == "table":
            return None
        return f"chunk {self.chunk_index}"

    def exact_location(self) -> str:
        """Human/citation-facing string -- the value Phase 6's
        `Citation.exact_location` column will ultimately hold."""
        if self.chunk_type == "table":
            return f"p.{self.page_number} ({self.table_cell_ref})"
        return f"p.{self.page_number} ({self.chunk_type}, {self.text_span})"

    def to_qdrant_payload(self) -> dict[str, Any]:
        """Flat, filterable fields for a Qdrant point's payload. Keys are
        namespaced with a `loc_` prefix so they can't collide with the
        other payload fields `qdrant_writer.py` adds alongside these
        (ticker, document_type, fiscal_year, ...)."""
        return {
            "loc_document_id": str(self.document_id),
            "loc_page_number": self.page_number,
            "loc_chunk_type": self.chunk_type,
            "loc_chunk_index": self.chunk_index,
            "loc_table_cell_ref": self.table_cell_ref,
        }

    @classmethod
    def from_qdrant_payload(cls, payload: dict[str, Any]) -> SourceLocation:
        """The read-side counterpart to `to_qdrant_payload` -- reconstructs
        a `SourceLocation` from a retrieved Qdrant point's payload. Not
        exercised by anything in Phase 5 (there is no reader yet); included
        now so the shape is symmetric from day one instead of guessed at
        again when Phase 6's retrieval code needs it."""
        return cls(
            document_id=uuid.UUID(payload["loc_document_id"]),
            page_number=payload["loc_page_number"],
            chunk_type=payload["loc_chunk_type"],
            chunk_index=payload["loc_chunk_index"],
            table_cell_ref=payload.get("loc_table_cell_ref"),
        )
