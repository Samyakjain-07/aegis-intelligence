"""Maps a retrieved/cited chunk back to its `source_location` -- the
read-path counterpart to `docs/architecture.md` §2's "this identifier
travels unchanged ... into the final citation object," implemented on the
write side by `tasks/ingest_document.py` (Phase 5).

For `NARRATIVE`/`FOOTNOTE` chunks, every field `SourceLocation` needs
(`document_id`, `page_number`, `chunk_type`, `chunk_index`) already lives
on the Postgres `DocumentChunk` row this module receives -- no extra I/O.
For `TABLE` chunks, `table_cell_ref` (e.g. `"table 0"`) does **not** live
in Postgres at all -- it's only ever written into Qdrant's payload at
ingestion time (`SourceLocation.to_qdrant_payload()`, called from
`tasks/ingest_document.py`). Rather than re-deriving or guessing that
value here -- which would quietly violate "never regenerated or
re-derived" the moment ingestion's table-indexing logic ever changed --
this module fetches the chunk's own Qdrant point by ID (`chunk_id` *is*
the Qdrant point ID, by construction; see `qdrant_writer.py`) and
reconstructs the exact `SourceLocation` ingestion originally wrote, via
`SourceLocation.from_qdrant_payload` -- the read-side counterpart Phase 5
built specifically for this moment. This is why a BM25-only retrieval hit
(Postgres has no Qdrant payload attached to it) still resolves a fully
correct citation for a table chunk: the lookup happens here, uniformly,
regardless of which retriever originally surfaced the chunk.
"""
from __future__ import annotations

import logging

from aegis_shared.source_location import SourceLocation

from src.core.dense_retriever import QDRANT_COLLECTION, get_qdrant_client
from src.core.types import RetrievedChunk
from src.models.db.enums import ChunkType
from src.observability.tracing import traced_stage

logger = logging.getLogger(__name__)

_SNIPPET_MAX_LENGTH = 400


def _fallback_source_location(chunk: RetrievedChunk) -> SourceLocation:
    """Only reached if a TABLE chunk's Qdrant point can't be found (its
    `embedding_vector_id` write never completed, or the point was later
    deleted) -- `table_cell_ref` is genuinely unknown in that case, so
    it's marked as such explicitly rather than guessed at."""
    return SourceLocation(
        document_id=chunk.document_id,
        page_number=chunk.page_number,
        chunk_type="table",
        chunk_index=chunk.chunk_index,
        table_cell_ref="table (unresolved)",
    )


@traced_stage("citation_resolver.resolve_source_location")
def resolve_source_location(chunk: RetrievedChunk) -> SourceLocation:
    """One chunk -> its `SourceLocation`. Cheap (no I/O) for
    `NARRATIVE`/`FOOTNOTE` chunks; costs one Qdrant point lookup for
    `TABLE` chunks (see module docstring) -- called only for the handful
    of chunks that made it into a final answer's citations, never for
    every raw retrieval candidate.
    """
    if chunk.chunk_type != ChunkType.TABLE:
        return SourceLocation(
            document_id=chunk.document_id,
            page_number=chunk.page_number,
            chunk_type=chunk.chunk_type.value,
            chunk_index=chunk.chunk_index,
        )

    client = get_qdrant_client()
    try:
        points = client.retrieve(
            collection_name=QDRANT_COLLECTION,
            ids=[str(chunk.chunk_id)],
            with_payload=True,
        )
    except Exception:
        logger.warning(
            "Qdrant point lookup failed for chunk_id=%s; using an unresolved table_cell_ref.",
            chunk.chunk_id,
            exc_info=True,
        )
        return _fallback_source_location(chunk)

    if not points or not points[0].payload:
        logger.warning(
            "No Qdrant point/payload found for chunk_id=%s; using an unresolved table_cell_ref.",
            chunk.chunk_id,
        )
        return _fallback_source_location(chunk)

    return SourceLocation.from_qdrant_payload(points[0].payload)


def exact_location_for(chunk: RetrievedChunk) -> str:
    """The human/citation-facing string -- what `Citation.exact_location`
    (the Postgres column) ultimately holds."""
    return resolve_source_location(chunk).exact_location()


def build_snippet(chunk: RetrievedChunk) -> str:
    """The citation's stored `snippet`: chunk content truncated to a
    display-reasonable length, not the full chunk. Stored directly on the
    `Citation` row (`citation.py`'s design: a citation is a self-contained,
    truthful record of what was actually shown to the user, not a live
    lookup through `chunk_id` that could later change or disappear)."""
    content = chunk.content.strip()
    if len(content) <= _SNIPPET_MAX_LENGTH:
        return content
    return content[:_SNIPPET_MAX_LENGTH].rstrip() + "..."
