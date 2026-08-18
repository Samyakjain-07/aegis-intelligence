"""Cohere rerank -- cross-encoder reordering of the RRF-fused hybrid
candidates (`docs/architecture.md` §1 Pipeline B step 4). This is what
`PROJECT_HANDBOOK.md` §2 names as Cohere rerank's whole reason for being
in the stack: the same metric ("data center revenue") can appear near-
identically across several quarters' filings, and pure vector similarity
can't tell them apart -- rerank scores each candidate against the
*actual* query text with a cross-encoder, which is what actually
distinguishes "the quarter this question is about" from "a quarter that
merely uses similar words."
"""
from __future__ import annotations

import logging
import os

import cohere
from dotenv import load_dotenv

from src.core.types import RetrievedChunk
from src.observability.tracing import traced_stage

load_dotenv()

logger = logging.getLogger(__name__)

COHERE_API_KEY: str = os.environ.get("COHERE_API_KEY", "")
COHERE_RERANK_MODEL: str = os.environ.get("COHERE_RERANK_MODEL", "rerank-v3.5")

_client: cohere.ClientV2 | None = None


def _get_client() -> cohere.ClientV2 | None:
    global _client
    if not COHERE_API_KEY:
        return None
    if _client is None:
        _client = cohere.ClientV2(api_key=COHERE_API_KEY)
    return _client


def _document_text(chunk: RetrievedChunk) -> str:
    """What Cohere actually scores against the query. A light metadata
    header (ticker/document type/page) is prepended alongside the content
    -- rerank benefits from that signal too, e.g. telling apart "NVDA Q4
    FY24" text from near-identical "AMD Q4 FY24" text that a pure content
    comparison might not separate as clearly."""
    header = f"{chunk.ticker} {chunk.document_type.value} p.{chunk.page_number}"
    return f"{header}\n{chunk.content}"


@traced_stage("reranker.rerank")
def rerank(query_text: str, candidates: list[RetrievedChunk], top_n: int = 8) -> list[RetrievedChunk]:
    """Reorders `candidates` by Cohere rerank relevance, populates
    `rerank_score` on each, and returns the top `top_n`.

    Falls back to the incoming RRF-fused order (already on `rrf_score`)
    if `COHERE_API_KEY` is unset or the call fails. This is a deliberately
    different failure mode than `dense_retriever.py`'s hard requirement on
    Cohere: there is no meaningful *retrieval* without an embedding, but
    reranking is a quality refinement layered on top of retrieval that
    already succeeded -- skipping it degrades ranking quality, not
    correctness, so it degrades gracefully rather than failing the
    request. Matches the "optional-quality provider call, deterministic
    fallback" pattern `agentic_chunker.py` established in Phase 5.
    """
    if not candidates:
        return []

    client = _get_client()
    if client is None:
        logger.info("COHERE_API_KEY not set; skipping rerank, keeping RRF-fused order.")
        return sorted(candidates, key=lambda c: c.rrf_score or 0.0, reverse=True)[:top_n]

    try:
        response = client.rerank(
            model=COHERE_RERANK_MODEL,
            query=query_text,
            documents=[_document_text(c) for c in candidates],
            top_n=min(top_n, len(candidates)),
        )
    except Exception:
        logger.warning("Cohere rerank call failed; falling back to RRF-fused order.", exc_info=True)
        return sorted(candidates, key=lambda c: c.rrf_score or 0.0, reverse=True)[:top_n]

    reranked: list[RetrievedChunk] = []
    for result in response.results:
        chunk = candidates[result.index]
        chunk.rerank_score = result.relevance_score
        reranked.append(chunk)
    return reranked
