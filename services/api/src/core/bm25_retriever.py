"""Sparse (lexical) retrieval -- the BM25 half of hybrid search
(`docs/architecture.md` §1 Pipeline B step 3).

**Implementation decision, not the literal Okapi BM25 formula:**
Postgres full-text search (`to_tsvector`/`websearch_to_tsquery`/
`ts_rank_cd`) is used here instead of a real BM25 library (`rank_bm25`) or
a dedicated search engine (Elasticsearch/OpenSearch/Whoosh). This does
*not* trip `CLAUDE.md` §4's "no new dependency outside the agreed stack"
boundary -- Postgres is already the agreed relational store, and its
built-in text-search functions need no new package. `ts_rank_cd`'s
ranking function isn't Okapi BM25's exact formula (it weights term
frequency/proximity/document length differently), but it fills the same
architectural role: a sparse, exact-lexical-match signal that catches
what dense embeddings miss (exact tickers, dollar figures, defined terms
like "CoWoS") to fuse against the dense leg via RRF. The module is still
named `bm25_retriever.py` per `PROJECT_HANDBOOK.md`'s file list, since
that's the role it plays in the hybrid pipeline, not a claim about the
exact scoring formula inside it. See `docs/DECISIONS_LOG.md` for the full
reasoning and the GIN index (`migrations/versions/
3100d4408cc5_add_document_chunks_content_fts_index.py`) this depends on
for query performance.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.core.types import RankedChunk
from src.models.db.document_chunk import DocumentChunk


def search(db: Session, query_text: str, top_k: int = 30) -> list[RankedChunk]:
    """Ranks `document_chunks` by lexical match against `query_text`,
    highest-ranked first. Returns an empty list (not an error) if the
    query has no matchable lexical content after Postgres's text-search
    normalization (e.g. pure stopwords) -- `hybrid_retriever.py` treats an
    empty leg as "this retriever found nothing," not a failure, and falls
    back to whatever the dense leg found.
    """
    if not query_text.strip():
        return []

    tsvector = func.to_tsvector("english", DocumentChunk.content)
    tsquery = func.websearch_to_tsquery("english", query_text)
    rank = func.ts_rank_cd(tsvector, tsquery).label("rank")

    stmt = (
        select(DocumentChunk.chunk_id, rank)
        .where(tsvector.op("@@")(tsquery))
        .order_by(rank.desc())
        .limit(top_k)
    )
    rows = db.execute(stmt).all()
    return [RankedChunk(chunk_id=row.chunk_id, score=float(row.rank)) for row in rows]
