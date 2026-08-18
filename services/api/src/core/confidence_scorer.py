"""Combines the retrieval-confidence signal with `numeric_verifier.py`'s
claim-verification results into one final `confidence_score` +
`low_confidence` flag -- `docs/architecture.md` §3's "retrieval
confidence above threshold? ... tag the response as low-confidence"
decision point, extended with this project's numeric-traceability
guarantee (`CLAUDE.md` §1): a plausible-sounding answer with even one
unverified number is not a confident answer, no matter how relevant
retrieval looked.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.core.numeric_verifier import NumericClaimResult
from src.core.types import RetrievedChunk
from src.observability.tracing import traced_stage

# Below this, `low_confidence=True` even with zero numeric claims to check
# (e.g. a purely narrative question where retrieval itself was weak).
LOW_CONFIDENCE_THRESHOLD = 0.4

# An RRF-fused score is an unbounded sum of 1/(k+rank) terms (see rrf.py),
# not a 0..1 similarity -- used only when rerank was skipped (no
# COHERE_API_KEY / the rerank call failed). This is a crude but honest
# saturating normalization: "the top candidate was found near the top of
# more than one retriever's ranking" saturates toward confident; a single
# low-rank hit stays low. Calibrated by inspection, not against a labeled
# set -- Phase 8's eval harness is the right place to check whether this
# threshold actually correlates with real answer quality.
_RRF_SATURATION_SCORE = 0.05

# A verification failure caps confidence at this ceiling regardless of how
# strong retrieval looked, scaled further by how many of the claims made
# actually verified -- one wrong number should not be washed out by three
# right ones averaging over it.
_UNVERIFIED_CLAIM_CEILING = 0.35


@dataclass(frozen=True, slots=True)
class FinalConfidence:
    confidence_score: float
    low_confidence: bool


@traced_stage("confidence_scorer.retrieval_confidence")
def retrieval_confidence(chunks: list[RetrievedChunk]) -> float:
    """A [0, 1] "how relevant is the best candidate we actually found"
    signal, read *before* generation runs -- this is what
    `api/v1/routes/query.py` checks against a threshold to decide whether
    it's even worth calling `answer_generator.py`, versus returning an
    honest "not enough information in the corpus" response outright.
    """
    if not chunks:
        return 0.0
    top = chunks[0]
    if top.rerank_score is not None:
        # Cohere's rerank-v3.5 relevance scores are already a calibrated
        # 0..1-ish value; clamp defensively rather than trust that blindly.
        return max(0.0, min(1.0, top.rerank_score))
    return max(0.0, min(1.0, (top.rrf_score or 0.0) / _RRF_SATURATION_SCORE))


@traced_stage("confidence_scorer.score_final")
def score_final(
    retrieval_conf: float, numeric_results: list[NumericClaimResult]
) -> FinalConfidence:
    if numeric_results:
        verified_count = sum(1 for result in numeric_results if result.verified)
        verification_rate = verified_count / len(numeric_results)
        if verification_rate < 1.0:
            capped = min(retrieval_conf, _UNVERIFIED_CLAIM_CEILING) * verification_rate
            return FinalConfidence(confidence_score=round(capped, 4), low_confidence=True)

    return FinalConfidence(
        confidence_score=round(retrieval_conf, 4),
        low_confidence=retrieval_conf < LOW_CONFIDENCE_THRESHOLD,
    )
