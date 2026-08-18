"""Phase 8 eval harness (`PROJECT_HANDBOOK.md` §6): runs the gold Q&A set
(`services/api/tests/eval/eval_dataset.jsonl`) against the **real, live**
query pipeline over HTTP -- not by importing `core/` modules directly --
and reports retrieval-precision and groundedness scores.

**Why HTTP, not a direct import of `_handle_query`:** `eval/` sits
outside `services/api/` in the repo structure (`PROJECT_HANDBOOK.md` §4)
specifically because it's an external consumer of the deployed system,
the same relationship a real analyst's browser has to the API -- hitting
`POST /api/v1/query` exercises FastAPI's request validation, middleware
stack, and response serialization exactly as a real request would,
instead of a partial pipeline reachable only through this script's own
import path. It also means this harness needs no `sys.path` trick to
import `core/` pipeline internals -- only the small, already-established
one (`scripts/seed_dev_data.py`'s pattern) to reach `src.infra.db` and
`src.models.db.eval_result` for writing `EvalResult` rows afterward.

**Scoring has two modes, and always produces a number in either one:**
1. **RAGAS** (real LLM-judged `faithfulness`/`context_precision`, via
   `OPENAI_API_KEY` -- reusing the vendor already approved in this stack
   for generation, not a new one) when the `ragas`/`langchain-openai`
   packages are installed and a key is configured.
2. **Deterministic fallback** (`observability/metrics.py`'s
   `citation_hit_rate`/`deterministic_groundedness`, built entirely from
   the live `QueryResponse`'s own fields -- ticker-matched citations and
   `confidence_score`) when RAGAS can't run for any reason.

Mode 2 is not a lesser placeholder bolted on to satisfy an import that
might fail -- it is the same "no meaningful X without a key, but never a
hard failure" contract this codebase already uses for
`reranker.py`/`answer_generator.py`'s optional-provider calls, applied to
evaluation itself. `--fail-under` and CI (`.github/workflows/
eval-regression.yml`) work identically regardless of which mode produced
the numbers; the summary always states which one ran.

Usage (from the repo root, `services/api`'s venv activated so
`httpx`/SQLAlchemy/etc. are importable, and a real `uvicorn` already
running against real ingested data -- see `PROJECT_HANDBOOK.md` §5/§6):

    .\\services\\api\\venv\\Scripts\\Activate.ps1
    python eval\\ragas_runner.py
    python eval\\ragas_runner.py --api-url http://localhost:8001 --fail-under 0.5
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

import httpx

# eval/ragas_runner.py lives at the repo root's eval/ dir, but the code it
# needs (SessionLocal, the EvalResult model) lives under services/api/src
# -- not on sys.path by default for a script invoked as
# `python eval\ragas_runner.py` from the repo root. Same trick
# scripts/seed_dev_data.py already established for the same reason: insert
# services/api (not services/api/src) so `import src...` resolves the same
# way it does for services/api's own tests and Alembic env.py.
_SERVICES_API = Path(__file__).resolve().parents[1] / "services" / "api"
sys.path.insert(0, str(_SERVICES_API))

from sqlalchemy import select
from src.infra.db import SessionLocal
from src.models.db.eval_result import EvalResult
from src.observability.metrics import citation_hit_rate, deterministic_groundedness

_DATASET_PATH = Path(__file__).resolve().parents[1] / "services" / "api" / "tests" / "eval" / "eval_dataset.jsonl"
_DEFAULT_API_URL = "http://localhost:8000"
_QUERY_PATH = "/api/v1/query"  # main.py mounts query.router under /api/v1


@dataclass(frozen=True, slots=True)
class GoldItem:
    """One `eval_dataset.jsonl` line. Field names match that file's keys
    directly -- no renaming/reshaping between the dataset's on-disk shape
    and this runner's in-memory shape, so the dataset stays the single
    source of truth a reviewer can read without cross-referencing this
    file too.
    """

    id: str
    category: str  # "numeric" | "narrative" | "negative_control"
    ticker: str | None
    question: str
    ground_truth: str
    expected_ticker: str | None
    expected_keywords: list[str]
    notes: str = ""


@dataclass(slots=True)
class EvalOutcome:
    """One gold item's result against the live pipeline. `retrieval_precision`/
    `groundedness_score` start as the deterministic fallback values and are
    overwritten in place by `_try_ragas_scores`'s caller when RAGAS
    successfully scored this item -- so every field is always populated
    with *some* real number, never `None`, by the time this is reported or
    persisted.
    """

    item: GoldItem
    query_id: uuid.UUID | None
    answer_text: str
    confidence_score: float
    citation_tickers: list[str]
    contexts: list[str]
    keyword_hit: bool
    retrieval_precision: float
    groundedness_score: float
    scored_by_ragas: bool = False
    error: str | None = None


def load_dataset(path: Path = _DATASET_PATH) -> list[GoldItem]:
    items: list[GoldItem] = []
    with path.open("r", encoding="utf-8") as fh:
        for line_number, raw_line in enumerate(fh, start=1):
            stripped = raw_line.strip()
            if not stripped:
                continue
            try:
                raw = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON -- {exc}") from exc
            items.append(
                GoldItem(
                    id=raw["id"],
                    category=raw["category"],
                    ticker=raw.get("ticker"),
                    question=raw["question"],
                    ground_truth=raw["ground_truth"],
                    expected_ticker=raw.get("expected_ticker"),
                    expected_keywords=list(raw.get("expected_keywords", [])),
                    notes=raw.get("notes", ""),
                )
            )
    return items


def _keyword_check(answer_text: str, item: GoldItem) -> bool:
    """`"negative_control"` items pass if *any* expected keyword appears
    (several different honest phrasings of "I don't know" are all
    correct -- see eval_dataset.jsonl's eval-012 note); every other
    category requires *all* expected keywords present, since those are
    specific facts the answer must actually state, not alternatives.
    """
    if not item.expected_keywords:
        return True
    lowered = answer_text.lower()
    if item.category == "negative_control":
        return any(keyword.lower() in lowered for keyword in item.expected_keywords)
    return all(keyword.lower() in lowered for keyword in item.expected_keywords)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def evaluate_item(client: httpx.Client, item: GoldItem) -> EvalOutcome:
    """Runs one gold question through the real, live `POST /api/v1/query`
    -- a fresh conversation every time (no `conversation_id` passed), same
    as `submit_query`'s "no reformulation, straight to the pipeline" path.
    Never raises: a request failure (API not running, 5xx, timeout)
    produces an `EvalOutcome` with `error` set and zero scores, so one bad
    item doesn't abort the rest of the run.
    """
    try:
        response = client.post(_QUERY_PATH, json={"query_text": item.question}, timeout=120.0)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:  # noqa: BLE001 -- deliberately broad, see docstring
        return EvalOutcome(
            item=item,
            query_id=None,
            answer_text="",
            confidence_score=0.0,
            citation_tickers=[],
            contexts=[],
            keyword_hit=False,
            retrieval_precision=0.0,
            groundedness_score=0.0,
            error=f"{type(exc).__name__}: {exc}",
        )

    citations = payload.get("citations", [])
    citation_tickers = [str(citation["ticker"]) for citation in citations]
    contexts = [str(citation["snippet"]) for citation in citations]
    answer_text = str(payload.get("answer_text", ""))
    confidence_score = _clamp01(float(payload.get("confidence_score", 0.0)))
    query_id_raw = payload.get("query_id")

    return EvalOutcome(
        item=item,
        query_id=uuid.UUID(query_id_raw) if query_id_raw else None,
        answer_text=answer_text,
        confidence_score=confidence_score,
        citation_tickers=citation_tickers,
        contexts=contexts,
        keyword_hit=_keyword_check(answer_text, item),
        retrieval_precision=citation_hit_rate(citation_tickers, item.expected_ticker),
        groundedness_score=deterministic_groundedness(confidence_score),
    )


def _try_ragas_scores(outcomes: list[EvalOutcome]) -> None:
    """Best-effort RAGAS overlay -- mutates `outcomes` in place
    (`retrieval_precision`/`groundedness_score`/`scored_by_ragas`) for
    every item RAGAS successfully judged; leaves the deterministic
    fallback values untouched for everything else (including every item
    if RAGAS can't run at all). Never raises -- see module docstring's
    "two modes, always produces a number" contract.
    """
    if not os.environ.get("OPENAI_API_KEY"):
        print("[ragas_runner] OPENAI_API_KEY not set; using deterministic fallback metrics (no LLM judge).")
        return

    try:
        from datasets import Dataset
        from langchain_openai import ChatOpenAI
        from ragas import evaluate as ragas_evaluate
        from ragas.llms import LangchainLLMWrapper
        from ragas.metrics import context_precision, faithfulness
    except ImportError as exc:
        print(
            f"[ragas_runner] RAGAS/langchain-openai not installed ({exc}); "
            "using deterministic fallback metrics. Run `pip install -r services/api/requirements.txt` "
            "to enable LLM-judged scoring."
        )
        return

    # RAGAS's faithfulness/context_precision need non-empty contexts to
    # judge against -- an item with zero citations (a correctly-declined
    # negative_control question, or a genuinely failed retrieval) has
    # nothing for an LLM judge to check the answer against, so it keeps
    # its deterministic score (citation_hit_rate already handles the
    # zero-citations case correctly for both outcomes -- see that
    # function's docstring) rather than being sent to RAGAS at all.
    scorable = [outcome for outcome in outcomes if outcome.contexts and not outcome.error]
    if not scorable:
        print("[ragas_runner] No items had citations to judge; using deterministic fallback metrics.")
        return

    try:
        dataset = Dataset.from_dict(
            {
                "question": [outcome.item.question for outcome in scorable],
                "answer": [outcome.answer_text for outcome in scorable],
                "contexts": [outcome.contexts for outcome in scorable],
                "ground_truth": [outcome.item.ground_truth for outcome in scorable],
            }
        )
        judge = LangchainLLMWrapper(
            ChatOpenAI(model=os.environ.get("OPENAI_CHAT_MODEL", "gpt-4o-mini"), temperature=0)
        )
        result = ragas_evaluate(dataset, metrics=[faithfulness, context_precision], llm=judge)
        if not hasattr(result, "to_pandas"):
            # ragas.evaluate()'s return type is a union (`EvaluationResult |
            # Executor`) in its own type stubs -- the `Executor` branch is
            # an internal-async-batching detail this synchronous call never
            # actually hits, but mypy can't know that statically. Treated
            # as a RAGAS-side failure (caught below) rather than silenced
            # with a bare `# type: ignore`, so an actual future API change
            # here still surfaces as "falling back," not a crash.
            raise TypeError(f"ragas.evaluate() returned {type(result).__name__}, expected a result with .to_pandas()")
        result_df = result.to_pandas()  # type: ignore[union-attr]
    except Exception as exc:  # noqa: BLE001 -- any RAGAS/OpenAI-side failure degrades, doesn't crash the run
        print(f"[ragas_runner] RAGAS evaluation call failed ({type(exc).__name__}: {exc}); using deterministic fallback metrics.")
        return

    for outcome, (_, row) in zip(scorable, result_df.iterrows()):
        faith = row.get("faithfulness")
        precision = row.get("context_precision")
        if faith is not None and not math.isnan(faith):
            outcome.groundedness_score = _clamp01(float(faith))
            outcome.scored_by_ragas = True
        if precision is not None and not math.isnan(precision):
            outcome.retrieval_precision = _clamp01(float(precision))
            outcome.scored_by_ragas = True


def _write_eval_results(outcomes: list[EvalOutcome]) -> int:
    """Persists one `EvalResult` row per successfully-scored item, upserting
    on `query_id` (its `unique=True` FK) so re-running this script against
    the same dataset doesn't grow duplicate rows -- the same idempotency
    concern `scripts/seed_dev_data.py` solved for `Document` rows, applied
    here to `EvalResult`. This is what makes `admin.py`'s
    `_flagged_condition()` `EvalResult.flagged_by_human` branch (Phase 7,
    present-but-dormant until now) actually exercised for the first time:
    every row this writes is a real, queryable `EvalResult` a human
    reviewer could later flag through that same code path.
    """
    db = SessionLocal()
    written = 0
    try:
        for outcome in outcomes:
            if outcome.error or outcome.query_id is None:
                continue
            existing = db.execute(
                select(EvalResult).where(EvalResult.query_id == outcome.query_id)
            ).scalar_one_or_none()
            if existing is not None:
                existing.retrieval_precision = outcome.retrieval_precision
                existing.groundedness_score = outcome.groundedness_score
            else:
                db.add(
                    EvalResult(
                        query_id=outcome.query_id,
                        retrieval_precision=outcome.retrieval_precision,
                        groundedness_score=outcome.groundedness_score,
                        flagged_by_human=False,
                    )
                )
            written += 1
        db.commit()
    finally:
        db.close()
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--api-url",
        default=os.environ.get("EVAL_API_URL", _DEFAULT_API_URL),
        help=f"Base URL of a running `uvicorn src.main:app` (default: {_DEFAULT_API_URL}, or $EVAL_API_URL).",
    )
    parser.add_argument(
        "--fail-under",
        type=float,
        default=float(os.environ.get("EVAL_FAIL_UNDER", "0.0")),
        help=(
            "Exit non-zero if mean retrieval_precision or mean groundedness_score "
            "falls below this [0,1] threshold -- the CI eval-regression gate "
            "(.github/workflows/eval-regression.yml) sets this; default 0.0 "
            "means 'report only, never fail' for ad-hoc local runs."
        ),
    )
    parser.add_argument(
        "--no-write-db",
        action="store_true",
        help="Skip persisting EvalResult rows (report only). Requires a reachable Postgres by default.",
    )
    args = parser.parse_args(argv)

    items = load_dataset()
    print(f"Loaded {len(items)} gold Q&A item(s) from {_DATASET_PATH}")
    print(f"Querying live API at {args.api_url}{_QUERY_PATH} ...\n")

    outcomes: list[EvalOutcome] = []
    with httpx.Client(base_url=args.api_url) as client:
        for item in items:
            outcome = evaluate_item(client, item)
            outcomes.append(outcome)
            if outcome.error:
                status = "ERROR"
            elif outcome.keyword_hit:
                status = "PASS"
            else:
                status = "FAIL"
            detail = f" -- {outcome.error}" if outcome.error else ""
            print(
                f"[{status}] {item.id:<10} ({item.category:<17} ticker={item.ticker or '-':<5}) "
                f"precision={outcome.retrieval_precision:.2f} groundedness={outcome.groundedness_score:.2f}{detail}"
            )

    _try_ragas_scores(outcomes)
    used_ragas = any(outcome.scored_by_ragas for outcome in outcomes)

    scored = [outcome for outcome in outcomes if not outcome.error]
    errored = [outcome for outcome in outcomes if outcome.error]
    mean_precision = sum(outcome.retrieval_precision for outcome in scored) / len(scored) if scored else 0.0
    mean_groundedness = sum(outcome.groundedness_score for outcome in scored) / len(scored) if scored else 0.0
    keyword_passes = sum(1 for outcome in scored if outcome.keyword_hit)

    print("\n=== Aegis Intelligence -- Phase 8 eval summary ===")
    print(f"Items scored:              {len(scored)}/{len(outcomes)} ({len(errored)} errored)")
    print(f"Scoring mode:               {'RAGAS (LLM-judged faithfulness + context_precision)' if used_ragas else 'deterministic fallback (ticker-matched citations / confidence_score)'}")
    print(f"Mean retrieval_precision:   {mean_precision:.3f}")
    print(f"Mean groundedness_score:    {mean_groundedness:.3f}")
    print(f"Keyword-check pass rate:    {keyword_passes}/{len(scored)}")

    if not args.no_write_db:
        written = _write_eval_results(outcomes)
        print(f"\nWrote/updated {written} EvalResult row(s) in Postgres.")

    failed = False
    if errored:
        print(f"\nFAIL: {len(errored)} item(s) could not reach the API -- is `uvicorn src.main:app` running at {args.api_url}?")
        failed = True
    if mean_precision < args.fail_under or mean_groundedness < args.fail_under:
        print(f"\nFAIL: a mean score fell below --fail-under={args.fail_under}")
        failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
