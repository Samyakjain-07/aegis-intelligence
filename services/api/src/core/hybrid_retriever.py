"""Hybrid retrieval -- runs BM25 and dense retrieval in parallel for
every query text passed in, fuses all of it via RRF, then hydrates the
fused top-N chunk_ids into full `RetrievedChunk`s from Postgres in a
single batched query.

`retrieve()` takes a *list* of query texts, not one -- `query_variants[0]`
is the primary (possibly history-reformulated) question; any further
entries are `multi_query.py`'s expansions. This lets one function serve
both the plain single-query path and the multi-query path uniformly:
every variant's BM25 leg and dense leg become one more ranked list fed
into the same RRF fusion, rather than multi-query needing its own
separate fusion-of-fusions step.
"""
from __future__ import annotations

import logging
import uuid
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from src.core import bm25_retriever, dense_retriever, rrf
from src.core.types import RankedChunk, RetrievedChunk
from src.models.db.document import Document
from src.models.db.document_chunk import DocumentChunk
from src.observability.tracing import traced_stage

logger = logging.getLogger(__name__)

_BM25_TOP_K = 30
_DENSE_TOP_K = 30


def _run_bm25(db: Session, query_text: str) -> list[RankedChunk]:
    """Never raises -- a down/misbehaving lexical-search leg degrades to
    "found nothing" rather than failing the whole request; the dense leg
    alone is still a usable (if weaker) retrieval result. Logged as a
    warning so the degradation is visible in practice, not silent."""
    try:
        return bm25_retriever.search(db, query_text, top_k=_BM25_TOP_K)
    except Exception:
        logger.warning("BM25 retrieval failed for %r; continuing dense-only.", query_text, exc_info=True)
        return []


def _run_dense(query_text: str) -> list[RankedChunk]:
    """Same degrade-don't-fail contract as `_run_bm25`, for the dense leg
    (a Cohere or Qdrant hiccup shouldn't 500 the whole query)."""
    try:
        return dense_retriever.search(query_text, top_k=_DENSE_TOP_K)
    except Exception:
        logger.warning("Dense retrieval failed for %r; continuing BM25-only.", query_text, exc_info=True)
        return []


def _hydrate(
    db: Session,
    fused: list[RankedChunk],
    primary_bm25: dict[uuid.UUID, float],
    primary_dense: dict[uuid.UUID, float],
) -> list[RetrievedChunk]:
    """One batched Postgres fetch (`chunk_id IN (...)`), joining `Document`
    (+`Company`, for ticker/title display) and `TableData` (the *complete*
    table for table chunks -- `numeric_verifier.py` needs the full table,
    not `DocumentChunk.content`'s truncated embedding-summary text for
    table chunks; see `table_chunker.py`'s docstring for why those differ).
    Re-sorted back into fused-rank order afterward since a SQL `IN` gives
    no ordering guarantee.
    """
    if not fused:
        return []
    chunk_ids = [ranked.chunk_id for ranked in fused]
    rows = (
        db.execute(
            select(DocumentChunk)
            .options(
                joinedload(DocumentChunk.document).joinedload(Document.company),
                joinedload(DocumentChunk.table_data),
            )
            .where(DocumentChunk.chunk_id.in_(chunk_ids))
        )
        .unique()
        .scalars()
        .all()
    )
    by_id = {row.chunk_id: row for row in rows}

    hydrated: list[RetrievedChunk] = []
    for ranked in fused:
        row = by_id.get(ranked.chunk_id)
        if row is None:
            # Retrieved (Qdrant/FTS index) but gone from Postgres by the
            # time we hydrate -- a real, if rare, race (e.g. re-ingestion
            # deleted+recreated chunks between the two reads). Skip rather
            # than error the whole request over one stale candidate.
            logger.warning("chunk_id=%s ranked but not found in Postgres at hydration time; skipping.", ranked.chunk_id)
            continue
        document = row.document
        hydrated.append(
            RetrievedChunk(
                chunk_id=row.chunk_id,
                document_id=row.document_id,
                chunk_type=row.chunk_type,
                content=row.content,
                page_number=row.page_number,
                chunk_index=row.chunk_index,
                ticker=document.company.ticker,
                document_title=document.title,
                document_type=document.document_type,
                fiscal_year=document.fiscal_year,
                fiscal_quarter=document.fiscal_quarter,
                table_data=row.table_data.raw_table_json if row.table_data is not None else None,
                bm25_score=primary_bm25.get(ranked.chunk_id),
                dense_score=primary_dense.get(ranked.chunk_id),
                rrf_score=ranked.score,
            )
        )
    return hydrated


@traced_stage("hybrid_retriever.retrieve", run_type="retriever")
def retrieve(db: Session, query_variants: list[str], top_n: int = 20) -> list[RetrievedChunk]:
    """`query_variants[0]` is the primary question (its own BM25/dense
    scores are attached to the returned chunks, for observability/
    debugging); any additional variants only widen the RRF candidate pool
    and influence ranking -- a per-expansion score isn't a meaningful
    thing to show a user or log per chunk.

    Each variant's BM25 (Postgres, via `db`) and dense (Cohere+Qdrant) legs
    run concurrently in a 2-worker thread pool. This is safe despite
    SQLAlchemy's `Session` not being safe for *concurrent* use: `db` is
    only ever touched by the BM25 worker thread while its future is
    pending -- the calling thread blocks on `.result()` rather than
    touching `db` itself, so there is never more than one thread actively
    using the session at once, only sequential handoffs across threads.
    """
    all_ranked_lists: list[list[RankedChunk]] = []
    primary_bm25: dict[uuid.UUID, float] = {}
    primary_dense: dict[uuid.UUID, float] = {}

    for index, variant in enumerate(query_variants):
        with ThreadPoolExecutor(max_workers=2) as pool:
            bm25_future = pool.submit(_run_bm25, db, variant)
            dense_future = pool.submit(_run_dense, variant)
            bm25_ranked = bm25_future.result()
            dense_ranked = dense_future.result()

        if index == 0:
            primary_bm25 = {ranked.chunk_id: ranked.score for ranked in bm25_ranked}
            primary_dense = {ranked.chunk_id: ranked.score for ranked in dense_ranked}

        all_ranked_lists.append(bm25_ranked)
        all_ranked_lists.append(dense_ranked)

    fused = rrf.reciprocal_rank_fusion(all_ranked_lists, top_n=top_n)
    return _hydrate(db, fused, primary_bm25, primary_dense)
