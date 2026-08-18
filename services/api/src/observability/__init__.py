"""Phase 8 observability: LangSmith tracing hooks (`tracing.py`) over the
Phase 6 query pipeline, and structured per-query latency/hit-rate/
groundedness logging (`metrics.py`).

Deliberately separate from `core/` -- these modules *watch* the pipeline
(`api/v1/routes/query.py` and the `core/` stages it calls), they don't
implement any of its retrieval/generation logic themselves. Matches
`PROJECT_HANDBOOK.md` §4's repo map (`services/api/src/{api,core,models,
infra,observability}/`).
"""
from __future__ import annotations
