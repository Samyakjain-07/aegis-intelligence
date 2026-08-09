"""The Phase 6 query/generation pipeline (`docs/architecture.md` §1
Pipeline B): history-aware reformulation -> multi-query expansion ->
hybrid retrieval (BM25 + dense, in parallel) -> RRF fusion -> Cohere
rerank -> confidence check -> grounded generation -> numeric verification
-> citation resolution.

Each stage is its own module, matching `PROJECT_HANDBOOK.md` §6's file
list exactly, wired together by `api/v1/routes/query.py` rather than by
this package re-exporting a combined pipeline function -- keeps every
stage independently importable/testable (see `docs/DECISIONS_LOG.md`).
"""
from __future__ import annotations
