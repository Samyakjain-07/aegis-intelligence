"""The real `ingest_document` Celery task -- replaces Phase 4's no-op
(`services/api/src/infra/celery_app.py::ingest_document_stub`), registered
under the exact same task name so anything already sitting in the Redis
queue from Phase 4 testing gets picked up unchanged (see
`src/infra/celery_app.py`'s docstring).

Orchestrates every pipeline stage in `docs/architecture.md` §1 steps 2-7,
in order: classify -> layout-segment -> extract tables -> chunk (agentic
narrative + footnote + table) -> embed (one batched pass) -> write
(Qdrant, then Postgres per chunk). `SourceLocation` is constructed exactly
once per chunk, right here, from data that's already final at that point
(`document_id`, `page_number`, `chunk_type`, `chunk_index`) -- and passed
unchanged into both `qdrant_writer.upsert_chunk_vector` and (via
`exact_location()`, in a future phase) `Citation.exact_location`. This is
the literal implementation of `docs/architecture.md` §2's "this identifier
travels unchanged ... it is never regenerated or re-derived."

`chunk_index` is assigned here, not by the individual chunkers
(`agentic_chunker.py`, `table_chunker.py`) -- it's one running counter per
page, shared across narrative, footnote, and table chunks landing on that
page, and only this orchestrator sees all three streams merged.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from aegis_shared.source_location import SourceLocation

from src.chunking.agentic_chunker import build_footnote_chunks, chunk_narrative_page
from src.chunking.table_chunker import TableChunkDraft, chunk_tables
from src.embedding.embedder import embed_texts
from src.infra.celery_app import celery_app
from src.infra.db import SessionLocal
from src.infra.storage import resolve_source_path
from src.parsing.document_classifier import classify_document, matches_declared_type
from src.parsing.layout_segmenter import segment_document
from src.parsing.pdf_parser import parse_pdf
from src.parsing.table_extractor import extract_tables
from src.storage.metadata_writer import (
    load_document_context,
    set_document_status,
    set_embedding_vector_id,
    upsert_document_chunk,
    upsert_table_data,
)
from src.storage.models import ChunkType, DocumentStatus
from src.storage.qdrant_writer import ensure_collection, upsert_chunk_vector

logger = logging.getLogger(__name__)


class _StatusTrackingTask(celery_app.Task):  # type: ignore[name-defined]
    """Marks the `Document` row `FAILED` only once Celery has genuinely
    given up (all `autoretry_for` retries exhausted) -- `on_failure` fires
    exactly then, not on every individual attempt. Status stays
    `PROCESSING` through transient retries (a Library-page user watching
    the status badge sees "Processing" the whole time, not a flicker back
    to failed-then-retrying), matching `docs/architecture.md` §3's
    "Corrupt or unparseable PDF -> retry queue with exponential backoff ->
    after N attempts, dead-letter queue + alert" -- the `FAILED` status
    here *is* the alert surface for now (see `docs/DECISIONS_LOG.md` for
    why a real dead-letter queue is deferred).
    """

    def on_failure(self, exc: Any, task_id: str, args: Any, kwargs: Any, einfo: Any) -> None:
        document_id = args[0] if args else kwargs.get("document_id")
        if document_id:
            session = SessionLocal()
            try:
                set_document_status(session, uuid.UUID(document_id), DocumentStatus.FAILED)
                session.commit()
            except Exception:
                logger.exception("Failed to mark document %s FAILED after exhausted retries.", document_id)
                session.rollback()
            finally:
                session.close()
        super().on_failure(exc, task_id, args, kwargs, einfo)  # type: ignore[misc]


@celery_app.task(
    name="ingest_document",
    bind=True,
    base=_StatusTrackingTask,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)
def ingest_document(self: Any, document_id: str) -> dict[str, Any]:
    doc_id = uuid.UUID(document_id)
    session = SessionLocal()
    try:
        context = load_document_context(session, doc_id)
        set_document_status(session, doc_id, DocumentStatus.PROCESSING)
        session.commit()

        pdf_path = resolve_source_path(context.source_url)
        parsed = parse_pdf(pdf_path)
        classification = classify_document(parsed)
        segments = segment_document(parsed)
        tables = extract_tables(pdf_path, segments.table_page_numbers)

        logger.info(
            "document=%s classified=%s (confidence=%.2f) pages=%d table_pages=%d tables_found=%d",
            doc_id,
            classification.kind.value,
            classification.confidence,
            parsed.page_count,
            len(segments.table_page_numbers),
            len(tables),
        )
        if not matches_declared_type(classification.kind, context.document_type):
            logger.warning(
                "document=%s content classified as %s but Document.document_type=%s "
                "-- mismatch logged, not treated as a failure (see document_classifier.py docstring).",
                doc_id, classification.kind.value, context.document_type,
            )

        # Build every chunk's draft content first, all embeddings computed
        # in one batched pass, before any DB/Qdrant writes -- keeps the
        # network calls (LLM, Cohere) out of the write transaction and
        # means a failure before this point has written nothing partial.
        chunk_specs: list[dict[str, Any]] = []
        for page in segments.pages:
            for draft in chunk_narrative_page(page.page_number, page.narrative_text):
                chunk_specs.append(
                    {"chunk_type": ChunkType.NARRATIVE, "page_number": draft.page_number,
                     "content": draft.content, "table": None}
                )
            for draft in build_footnote_chunks(page):
                chunk_specs.append(
                    {"chunk_type": ChunkType.FOOTNOTE, "page_number": draft.page_number,
                     "content": draft.content, "table": None}
                )
        for table_chunk in chunk_tables(tables):
            chunk_specs.append(
                {"chunk_type": ChunkType.TABLE, "page_number": table_chunk.page_number,
                 "content": table_chunk.content, "table": table_chunk}
            )

        if not chunk_specs:
            logger.warning("document=%s produced zero chunks (empty or unparseable content).", doc_id)

        embeddings = embed_texts([spec["content"] for spec in chunk_specs], input_type="search_document")
        ensure_collection()

        # Running chunk_index per page, shared across chunk_type streams
        # -- see module docstring.
        page_counters: dict[int, int] = {}
        written = 0
        for spec, vector in zip(chunk_specs, embeddings, strict=True):
            page_number: int = spec["page_number"]
            index = page_counters.get(page_number, 0)
            page_counters[page_number] = index + 1

            chunk_id = upsert_document_chunk(
                session,
                document_id=doc_id,
                chunk_type=spec["chunk_type"],
                content=spec["content"],
                page_number=page_number,
                chunk_index=index,
            )

            table_draft: TableChunkDraft | None = spec["table"]
            if table_draft is not None:
                upsert_table_data(
                    session,
                    chunk_id=chunk_id,
                    raw_table_json=table_draft.raw_table_json,
                    row_count=table_draft.row_count,
                    column_count=table_draft.column_count,
                )

            source_location = SourceLocation(
                document_id=doc_id,
                page_number=page_number,
                chunk_type=spec["chunk_type"].value,
                chunk_index=index,
                table_cell_ref=(f"table {table_draft.table_index}" if table_draft is not None else None),
            )
            upsert_chunk_vector(
                chunk_id=chunk_id,
                vector=vector,
                content=spec["content"],
                source_location=source_location,
                ticker=context.ticker,
                document_type=context.document_type,
                fiscal_year=context.fiscal_year,
                fiscal_quarter=context.fiscal_quarter,
            )
            set_embedding_vector_id(session, chunk_id, str(chunk_id))
            written += 1

        set_document_status(session, doc_id, DocumentStatus.COMPLETED)
        session.commit()
        return {
            "document_id": document_id,
            "status": "completed",
            "chunk_count": written,
            "table_count": len(tables),
            "classification": classification.kind.value,
        }
    except Exception:
        session.rollback()
        logger.exception("Ingestion failed for document=%s", doc_id)
        raise
    finally:
        session.close()
