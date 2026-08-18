"""LangSmith tracing hooks over the Phase 6 query pipeline
(`PROJECT_HANDBOOK.md` §6 Phase 8: "Add LangSmith or Arize Phoenix
tracing hooks in `observability/tracing.py`").

`traced_stage()` is a decorator, applied directly to each `core/` pipeline
stage function (`multi_query.expand_query`, `hybrid_retriever.retrieve`,
`reranker.rerank`, `answer_generator.generate_answer`,
`numeric_verifier.verify_answer`, `confidence_scorer.score_final`,
`citation_resolver.resolve_source_location`) -- not left present-but-
dormant in this file alone. Every real `POST /query` request is traced
end-to-end, stage by stage, once `LANGCHAIN_API_KEY` is set, exactly the
way `docs/DECISIONS_LOG.md`'s Phase 7 admin-analytics entries flagged as
the bar to clear ("exercised for the first time, not just present").

**A true no-op when tracing isn't configured** -- `traced_stage` returns
the wrapped function completely *unwrapped* (not a pass-through wrapper
that still pays call overhead) when `LANGCHAIN_TRACING_V2`/
`LANGCHAIN_API_KEY` aren't set or the `langsmith` package isn't
installed. This matters more here than for a typical optional-provider
call (`reranker.py`'s Cohere fallback, `answer_generator.py`'s OpenAI
fallback): those degrade *what the pipeline does* when unset; tracing
must never change *how* the pipeline behaves, only whether a side-channel
trace gets emitted -- so "disabled" has to mean "identical code path,"
not "a thinner wrapper still runs."
"""
from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Any, TypeVar

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Standard LangSmith env vars -- same names the `langsmith`/`langchain`
# SDKs read themselves, so a real LangSmith account only ever needs these
# three set (in .env, never committed -- see .env.example) for tracing to
# turn on; no Aegis-specific env var invented for the same job.
LANGCHAIN_TRACING_V2: bool = os.environ.get("LANGCHAIN_TRACING_V2", "").strip().lower() == "true"
LANGCHAIN_API_KEY: str = os.environ.get("LANGCHAIN_API_KEY", "")
LANGCHAIN_PROJECT: str = os.environ.get("LANGCHAIN_PROJECT", "aegis-intelligence")

_F = TypeVar("_F", bound=Callable[..., Any])

# Resolved once at import time, not re-checked per call -- matches
# reranker.py's COHERE_API_KEY / _get_client() module-level-constant
# pattern (env is read once at process start; a mid-process env change
# isn't a supported scenario anywhere else in this codebase either).
TRACING_ENABLED: bool = LANGCHAIN_TRACING_V2 and bool(LANGCHAIN_API_KEY)

_traceable: Callable[..., Any] | None = None
if TRACING_ENABLED:
    # LangSmith's own SDK reads LANGCHAIN_PROJECT/LANGCHAIN_API_KEY
    # straight from the environment -- setdefault (not overwrite) so an
    # operator's own explicit LANGCHAIN_PROJECT always wins over this
    # default.
    os.environ.setdefault("LANGCHAIN_PROJECT", LANGCHAIN_PROJECT)
    try:
        from langsmith import traceable as _traceable  # type: ignore[assignment]
    except ImportError:
        logger.warning(
            "LANGCHAIN_TRACING_V2=true and LANGCHAIN_API_KEY is set, but the "
            "`langsmith` package isn't installed (see services/api/requirements.txt) "
            "-- tracing disabled for this process."
        )
        TRACING_ENABLED = False


def traced_stage(name: str, run_type: str = "chain") -> Callable[[_F], _F]:
    """Marks one query-pipeline stage as a traced LangSmith run.

    `name` is the stage's identity in the LangSmith UI (e.g.
    `"hybrid_retriever.retrieve"`) -- deliberately `module.function`, not
    a hand-picked label, so a trace always names exactly the function that
    ran, the same discipline `numeric_verifier.py` uses for citation
    indices being positional-not-arbitrary. `run_type` follows LangSmith's
    own vocabulary (`"chain"`/`"llm"`/`"retriever"`); callers making an
    LLM or Qdrant/Postgres retrieval call pass the more specific type so
    LangSmith's UI renders it correctly (token counts for `"llm"`, etc.).
    """

    def decorator(func: _F) -> _F:
        if not TRACING_ENABLED or _traceable is None:
            return func
        return _traceable(name=name, run_type=run_type)(func)  # type: ignore[no-any-return]

    return decorator
