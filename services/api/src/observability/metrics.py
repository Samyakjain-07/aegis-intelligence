"""Latency/hit-rate/groundedness metrics for the query pipeline
(`PROJECT_HANDBOOK.md` §6 Phase 8).

No metrics backend (Prometheus, StatsD, ...) is in the agreed stack
(`CLAUDE.md` §3), so this is deliberately boring: a `StageTimer` context
manager that measures wall-clock latency per named stage and logs one
structured line per request, plus two pure, dependency-free functions
(`citation_hit_rate`, `deterministic_groundedness`) that turn a real
`QueryResponse`'s own fields into the "hit-rate"/"groundedness" numbers
`PROJECT_HANDBOOK.md` names -- reused by both the live pipeline
(`api/v1/routes/query.py`, one structured log line per request) and the
offline eval harness (`eval/ragas_runner.py`, the deterministic fallback
path when RAGAS/`OPENAI_API_KEY` aren't available). One definition of
each metric, not two independently-drifting ones.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Self

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class StageTimer:
    """Accumulates named-stage wall-clock durations for one request.

    Used as `with timer.stage("retrieval"): ...` around each pipeline
    phase in `_handle_query` (`api/v1/routes/query.py`); `log_summary()`
    emits one structured line per request with every stage's duration
    plus the total -- the "latency" metric `PROJECT_HANDBOOK.md` names,
    made inspectable without a metrics backend by going through the same
    `logging` module every other module in this codebase already uses.
    """

    durations_ms: dict[str, float] = field(default_factory=dict)
    _start: float = field(default_factory=time.perf_counter, repr=False)

    def stage(self, name: str) -> _StageContext:
        return _StageContext(self, name)

    def total_ms(self) -> float:
        return (time.perf_counter() - self._start) * 1000.0

    def log_summary(self, *, query_id: object, confidence_score: float, citation_count: int) -> None:
        """One structured line per request -- `query_id`/`confidence_score`/
        `citation_count` are logged alongside timings so a slow or
        low-confidence request can be found by grepping logs without a
        separate tracing backend (LangSmith, when configured via
        `observability/tracing.py`, is the richer per-stage view; this is
        the always-on, zero-dependency floor under it).
        """
        logger.info(
            "query_metrics query_id=%s total_ms=%.1f confidence_score=%.3f citation_count=%d stages=%s",
            query_id,
            self.total_ms(),
            confidence_score,
            citation_count,
            {name: round(ms, 1) for name, ms in self.durations_ms.items()},
        )


@dataclass(slots=True)
class _StageContext:
    """`StageTimer.stage(name)`'s context-manager body -- a private helper
    type, not meant to be constructed directly (hence the leading
    underscore, matching this codebase's existing `_Parsed*`/`_Stage*`
    private-dataclass convention, e.g. `numeric_verifier._ParsedNumber`)."""

    timer: StageTimer
    name: str
    _entered_at: float = field(default=0.0, repr=False)

    def __enter__(self) -> Self:
        self._entered_at = time.perf_counter()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.timer.durations_ms[self.name] = (time.perf_counter() - self._entered_at) * 1000.0


def citation_hit_rate(citation_tickers: list[str], expected_ticker: str | None) -> float:
    """The "hit-rate" metric `PROJECT_HANDBOOK.md` §6 Phase 8 names: did
    retrieval actually surface a citation from the company the question
    was really about?

    Matched on `CitationResponse.ticker` (a real `Company.ticker` value,
    e.g. `"ACME"`/`"ESOA"`), not `document_title` -- the gold set
    (`eval_dataset.jsonl`) was written against real ingested documents
    whose exact title strings were typed by hand at upload time and never
    recorded anywhere this eval harness can read back; the ticker is a
    controlled value the gold set's author (this decisions-log entry) can
    state with certainty, so it's what a substring match should be built
    on, not a guess at free-text a human entered once.

    `expected_ticker=None` models the gold set's negative-control case
    (an `"negative_control"`-category item, e.g. asking about a company
    never ingested) -- a **correct** answer there cites nothing at all, so
    the hit rate is 1.0 precisely when `citation_tickers` is empty, not
    when it happens to contain a ticker that can't exist by construction.
    Getting this inverted would silently reward the pipeline for
    hallucinating a citation on a question it should have declined to
    ground.
    """
    if expected_ticker is None:
        return 1.0 if not citation_tickers else 0.0
    if not citation_tickers:
        return 0.0
    matches = sum(1 for ticker in citation_tickers if ticker.upper() == expected_ticker.upper())
    return matches / len(citation_tickers)


def deterministic_groundedness(confidence_score: float) -> float:
    """The no-LLM-judge "groundedness" fallback: `confidence_score` *is*
    this project's own groundedness signal already -- `confidence_scorer.
    score_final` (Phase 6) folds `numeric_verifier.py`'s per-claim
    verification into it and numeric verification can only ever lower
    that score, never raise it (see that module's docstring). Reusing it
    here, rather than inventing a second groundedness formula, means the
    eval harness's fallback measures the exact same thing the live
    pipeline already computed for that request -- not an approximation of
    it. RAGAS's LLM-judged `faithfulness` score (`eval/ragas_runner.py`,
    when `OPENAI_API_KEY` is set) is the more independent measurement;
    this is the honest floor under it when that path can't run.
    """
    return max(0.0, min(1.0, confidence_score))
