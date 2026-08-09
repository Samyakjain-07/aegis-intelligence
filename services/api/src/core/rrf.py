"""Reciprocal Rank Fusion -- combines two or more independently-ranked
candidate lists (BM25's lexical ranking, dense retrieval's cosine-
similarity ranking, and, when `multi_query.py` expands the question, each
reformulation's own pair of rankings) into one fused ranking.

A pure function, not a class, and deliberately the one module in this
pipeline with zero I/O -- everything it needs is already in memory, which
is also exactly why it's the cheapest piece to unit-test in isolation
(`PROJECT_HANDBOOK.md`'s planned `tests/unit/test_rrf.py`).
"""
from __future__ import annotations

import uuid

from src.core.types import RankedChunk

# Standard RRF damping constant from the original paper (Cormack, Clarke &
# Buettcher, 2009) -- large enough that rank 1 vs. rank 2 in one list isn't
# wildly more valuable than rank 1 vs. rank 2 in another, small enough that
# rank still matters more than showing up in more lists at a low rank.
DEFAULT_K = 60


def reciprocal_rank_fusion(
    ranked_lists: list[list[RankedChunk]],
    k: int = DEFAULT_K,
    top_n: int | None = None,
) -> list[RankedChunk]:
    """Fuses `ranked_lists` by rank position, not by each list's raw score.

    This is RRF's entire point, not an oversight: BM25's `ts_rank_cd`
    output and a cosine-similarity score from Qdrant live on completely
    different, incomparable scales -- averaging or summing them directly
    would silently let whichever retriever happens to produce larger raw
    numbers dominate the fusion. Using each item's *rank* (1st, 2nd, 3rd,
    ...) within its own list instead makes every list's contribution
    scale-free and directly comparable: a chunk gets `1 / (k + rank)`
    "votes" from each list it appears in, summed across all lists.

    A chunk that appears in more than one input list (e.g. found by both
    BM25 and dense retrieval, or by dense retrieval for two different
    multi-query reformulations) accumulates a fused score from every
    appearance -- which is also RRF's implicit "the fact that multiple
    independent retrievers agree on this chunk is itself a signal" logic.
    """
    scores: dict[uuid.UUID, float] = {}
    for ranked_list in ranked_lists:
        for rank, item in enumerate(ranked_list, start=1):
            scores[item.chunk_id] = scores.get(item.chunk_id, 0.0) + 1.0 / (k + rank)

    fused = [RankedChunk(chunk_id=chunk_id, score=score) for chunk_id, score in scores.items()]
    fused.sort(key=lambda ranked: ranked.score, reverse=True)
    return fused[:top_n] if top_n is not None else fused
