# Progress Snapshot — 2026-08-09 (Phase 5)

> Repo state check: real git repository (`git log` shows one prior
> commit, `f80737c chore: initial commit`, plus an uncommitted Phase 4
> tree at the start of this phase). Verified by reading files and
> running each phase's own commands — `mypy`, `ruff`, and `pytest`
> (24/24 new unit tests, all passing) inside `services/ingestion`'s own
> venv, a real `pip install -e packages/shared` into that venv, and a
> **live end-to-end run against the real Docker infra**: Postgres,
> Qdrant, and Redis were already running (`docker compose ps`, confirmed
> healthy before starting anything). A real `uvicorn` (port 8001) and a
> real `celery -A src.infra.celery_app worker --pool=solo` were started;
> a synthetic 10-K-style PDF was generated (`pymupdf`, three pages: cover
> + narrative, risk-factors narrative + a footnote, MD&A narrative + a
> ruled 4-row financial table) and uploaded through a real multipart
> `POST /documents`. The worker picked it up and produced exactly the
> expected chunks — verified by reading the actual rows back out of
> Postgres and Qdrant, not just checking the task returned success (see
> the Phase 5 row below and `docs/DECISIONS_LOG.md`'s `tasks/
> ingest_document.py` entry for the full breakdown). Unplanned but
> instructive: the same worker also picked up two *stale* messages
> already sitting in Redis from Phase 4 testing — one a real document
> that processed successfully end-to-end (31 chunks, 4 tables), one a
> deleted test row that correctly retried 3x with exponential backoff
> then failed cleanly, confirming the retry/failure path live, not just
> in theory. Both background processes were stopped after verification;
> the Postgres/Qdrant/Redis containers were left running (untouched,
> pre-existing). Not verified by folder existence at any point.

## Build Order Status

| # | Phase | Status | Reason |
|---|-------|--------|--------|
| 1 | Fix Search crash | **Done** | Unchanged this phase. See `docs/DECISIONS_LOG.md` 2026-08-07 entry. |
| 2 | DB schema | **Done** | Unchanged this phase. See the seven `docs/DECISIONS_LOG.md` entries dated 2026-08-07. |
| 3 | FastAPI skeleton | **Done** | Unchanged this phase. See the `docs/DECISIONS_LOG.md` entry dated 2026-08-08. |
| 4 | Library page vertical slice | **Done** | Unchanged this phase. See the five `docs/DECISIONS_LOG.md` entries dated 2026-08-08 (Phase 4) plus the 2026-08-09 port-fix entry. |
| 5 | Ingestion pipeline | **Done** | Real Celery task ([tasks/ingest_document.py](../services/ingestion/src/tasks/ingest_document.py)) replaces Phase 4's no-op, registered under the same `"ingest_document"` name. Full pipeline — classify → layout-segment → extract tables (camelot) → agentic-chunk (OpenAI, heuristic fallback) → embed (Cohere) → write (Qdrant + Postgres, shared `SourceLocation`) — implemented and verified live against real Docker infra (see snapshot header). Eleven `docs/DECISIONS_LOG.md` entries dated 2026-08-09, one per stage. |
| 6 | Retrieval/generation pipeline | **Not Started** | `POST /query`/`POST /query/followup` exist as typed stubs (Phase 3) but return placeholder data; no retrieval or generation logic exists yet. Now has real ingested data (Phase 5's output) to retrieve against. |
| 7 | Remaining pages | **In Progress (UI-only)** | Chat, Compare, Admin all still hardcoded mock data. Unchanged this phase. |
| 8 | Eval/observability | **Not Started** | `eval/` directory exists, zero files. |
| 9 | Deployment | **Not Started** | No `Dockerfile`, no prod compose file, no `.github/workflows` files. |

## File Inventory

### packages/shared/ — Phase 5 output (new)

| Path | Status | Description |
|------|--------|-------------|
| [pyproject.toml](../packages/shared/pyproject.toml) | Complete (new) | `setuptools`-backed, editable-installable local package (`aegis-shared`). Installed via `-e ../../packages/shared` in `services/ingestion/requirements.txt`. `services/api` does not install it yet — see Immediate Next Step. |
| [aegis_shared/source_location.py](../packages/shared/aegis_shared/source_location.py) | Complete (new) | `SourceLocation` — the frozen dataclass every retrievable chunk's location is built from, once, at ingestion time (`docs/architecture.md` §2). `exact_location()`, `to_qdrant_payload()`, `from_qdrant_payload()`. Dependency-free by design. |
| [aegis_shared/py.typed](../packages/shared/aegis_shared/py.typed) | Complete (new) | PEP 561 marker, so `mypy` trusts this package's types from a consuming service. |

### services/ingestion/ — Phase 5 output (new; was `requirements.txt` + empty `venv/` only)

| Path | Status | Description |
|------|--------|-------------|
| [src/infra/db.py](../services/ingestion/src/infra/db.py), [celery_app.py](../services/ingestion/src/infra/celery_app.py), [storage.py](../services/ingestion/src/infra/storage.py) | Complete (new) | Sync SQLAlchemy engine/session (same `DATABASE_URL` as `services/api`, separate module — see decisions log); the consumer-side Celery app (`include=["src.tasks.ingest_document"]`); `resolve_source_path()`, the read-side counterpart to the API's `save_uploaded_pdf`. |
| [src/storage/models.py](../services/ingestion/src/storage/models.py) | Complete (new) | A second, independent set of SQLAlchemy 2.0 models (`Company`, `Document`, `DocumentChunk`, `TableData`) mirroring only the columns ingestion touches — deliberately not imported from `services/api`. See decisions log for the full reasoning. |
| [src/parsing/pdf_parser.py](../services/ingestion/src/parsing/pdf_parser.py) | Complete (new) | `parse_pdf()` — pymupdf structural parse: per-page text, font-annotated `TextLine`s, candidate table bboxes via `Page.find_tables()`. |
| [src/parsing/document_classifier.py](../services/ingestion/src/parsing/document_classifier.py) | Complete (new) | `classify_document()` — heuristic filing/transcript/deck/unknown classification; `matches_declared_type()` cross-checks against the analyst's upload-time `document_type` (logged, not enforced). |
| [src/parsing/layout_segmenter.py](../services/ingestion/src/parsing/layout_segmenter.py) | Complete (new) | `segment_document()`/`segment_page()` — narrative/footnote/table-region split per page, via font size, page position, and footnote-marker regex, plus bbox-overlap exclusion of table regions. |
| [src/parsing/table_extractor.py](../services/ingestion/src/parsing/table_extractor.py) | Complete (new) | `extract_tables()` — camelot, lattice-first with a stream fallback for low-accuracy pages, structured `headers`/`rows` output, never flattened. |
| [src/chunking/agentic_chunker.py](../services/ingestion/src/chunking/agentic_chunker.py) | Complete (new) | `chunk_narrative_page()` — OpenAI (`gpt-4o-mini`, JSON mode) section-boundary detection with a deterministic paragraph-boundary heuristic fallback (no key set / call fails / malformed response); `_enforce_size_bounds` applies uniformly to both paths. `build_footnote_chunks()` (no LLM). |
| [src/chunking/table_chunker.py](../services/ingestion/src/chunking/table_chunker.py) | Complete (new) | `chunk_table()`/`chunk_tables()` — one chunk per table, row-aligned splits (never mid-row) past 60 rows; `_embedding_text()` generates a flattened summary *only* as Cohere's embedding input, never the stored representation. |
| [src/embedding/embedder.py](../services/ingestion/src/embedding/embedder.py) | Complete (new) | `embed_texts()` — Cohere `embed-english-v3.0`, 1024-dim, batched, `input_type`-aware (`search_document` today; `search_query` reserved for Phase 6). |
| [src/storage/qdrant_writer.py](../services/ingestion/src/storage/qdrant_writer.py) | Complete (new) | `ensure_collection()` (creates `document_chunks`, cosine distance, payload indexes on `loc_document_id`/`ticker`/`document_type`/`loc_chunk_type`/`fiscal_year`/`fiscal_quarter`) and `upsert_chunk_vector()` — point ID is the chunk's own `chunk_id`. |
| [src/storage/metadata_writer.py](../services/ingestion/src/storage/metadata_writer.py) | Complete (new) | `load_document_context()`, `set_document_status()`, `upsert_document_chunk()`/`upsert_table_data()` (real `INSERT ... ON CONFLICT DO UPDATE`, idempotent re-ingestion), `set_embedding_vector_id()`. |
| [src/tasks/ingest_document.py](../services/ingestion/src/tasks/ingest_document.py) | Complete (new) | The real `ingest_document` Celery task — replaces Phase 4's no-op under the same task name. Orchestrates every stage above, assigns `chunk_index` per page, builds `SourceLocation` once per chunk, drives `Document.status` through `PENDING → PROCESSING → COMPLETED`/`FAILED` with `autoretry_for`/`retry_backoff` and a custom `on_failure` handler. |
| [pyproject.toml](../services/ingestion/pyproject.toml) | Complete (new) | `mypy`/`pytest` config, mirroring `services/api`'s — includes `mypy_path` pointing at `packages/shared`'s real source (see decisions log for why the editable install alone wasn't enough for `mypy`). |
| [requirements.txt](../services/ingestion/requirements.txt) | Updated | Added `openai>=1.50` and `-e ../../packages/shared`. |
| [tests/unit/test_source_location.py](../services/ingestion/tests/unit/test_source_location.py), [test_document_classifier.py](../services/ingestion/tests/unit/test_document_classifier.py), [test_layout_segmenter.py](../services/ingestion/tests/unit/test_layout_segmenter.py), [test_table_chunker.py](../services/ingestion/tests/unit/test_table_chunker.py), [test_agentic_chunker.py](../services/ingestion/tests/unit/test_agentic_chunker.py) | Complete (new) | 24 tests covering every pure-function pipeline piece (no live DB/Qdrant/API calls needed) — notably `test_table_chunker.py`'s 127-row split-boundary check and `test_agentic_chunker.py`'s heuristic-fallback/size-bound tests, both of which caught and fixed real bugs (see decisions log) before this phase's live smoke test. |

### Root — Phase 5 output

| Path | Status | Description |
|------|--------|-------------|
| [.env.example](../.env.example) | Updated | Removed the unused `EMBEDDING_API_KEY` placeholder (embedding provider decision resolved this phase — see decisions log); added `COHERE_EMBED_MODEL`/`OPENAI_API_KEY`/`OPENAI_CHUNKING_MODEL`/`QDRANT_COLLECTION` documentation (all optional, sane in-code defaults). |

### Everything else (unchanged this phase, re-verified where noted)

| Area | Status |
|------|--------|
| `services/api` | Unchanged. `POST /documents` still enqueues via the same `"ingest_document"` task name Phase 5's real worker now serves — re-verified live this phase (see snapshot header). |
| `frontend` | Unchanged. |
| `packages/shared` | New this phase (see above) — was empty. |
| `infra/k8s`, `infra/terraform` | Empty. |
| `eval` | Empty. |
| `.github/workflows` | Empty. |
| `docs` | `architecture.md`/`Financial_RAG_Project_Structure.md` unchanged. |
| `data/uploads/` | Gitignored. Now contains real processed PDFs from this phase's live smoke test in addition to Phase 4's, transiently — not committed. |

## Known Issues / Bugs

**Carried over, unchanged this phase:** the full frontend known-issue
checklist and Phase 4 notes from the previous snapshot (unused shadcn
components, disconnected dark-mode tokens, missing aria-labels, no
`GET /documents/{id}/file`, `GET /documents` not tenant-filtered by
design, `POST /documents`'s unguarded find-or-create race, local-disk
storage needing a Phase 9 rework) — see git history for the full table,
none fixed or newly introduced this phase.

**Phase 5-specific notes:**
- **No dead-letter queue.** `ingest_document`'s `autoretry_for`/
  `retry_backoff` retries transient failures (verified live: a stale
  message referencing a deleted document row retried 3x with backoff,
  1s/2s/3s, then gave up cleanly). Once retries are exhausted, the
  `Document.status = FAILED` row *is* the alert surface — Redis (unlike
  RabbitMQ) doesn't give a real dead-letter queue for free, and building
  one wasn't in this phase's scope. Revisit if silent `FAILED` rows
  become a real operational problem.
- **`autoretry_for=(Exception,)` doesn't distinguish retryable
  (transient API timeout) from deterministic (corrupt PDF, code bug)
  failures** — both get the same 3-retry treatment. Consistent with
  `docs/architecture.md` §3's stated retry behavior for a corrupt PDF,
  but means a deterministic bug wastes ~3 retry cycles before surfacing.
- **`OPENAI_API_KEY` is optional, not required** — if unset,
  `agentic_chunker.py` silently uses its heuristic paragraph-boundary
  fallback instead of real LLM-assisted boundaries. This phase's entire
  live smoke test ran through that fallback path (no key configured in
  this environment's `.env`) — ingestion works correctly either way, but
  chunk boundaries are only as good as the heuristic until a real key is
  added.
- **`services/api` does not yet install `packages/shared`** — nothing
  there needs `SourceLocation` until Phase 6's `citation_resolver.py`.
  Flagged explicitly in Immediate Next Step below so it isn't forgotten.
- **Table-region exclusion, footnote detection, and document
  classification are all heuristic**, tuned by inspection and this
  phase's unit/smoke tests, not against a labeled dataset — Phase 8's
  eval harness is the natural point to measure whether any of these
  heuristics are actually costing retrieval precision.
- **No per-document integration test in CI** — this phase's end-to-end
  verification was a live, manual run against real Docker infra (see
  snapshot header), not an automated test that runs on every change.
  Phase 8 (eval) or a dedicated CI integration-test pass could formalize
  this; out of scope for Phase 5 itself per `PROJECT_HANDBOOK.md`.

**Grep for TODO/FIXME/XXX/NotImplementedError/bare `pass`:** No matches
under `services/ingestion/src` or `packages/shared` (checked as part of
this phase).

## Deviations From the Original Plan

- **Two new external dependencies (Cohere embeddings, OpenAI chunking)
  were added this phase, both after asking Sam directly** — `CLAUDE.md`
  §4 requires stopping before adding a dependency outside the agreed
  stack, and neither the embedding provider (explicitly flagged
  undecided since Phase 2) nor an LLM vendor for agentic chunking
  (never named anywhere) had been resolved yet. Full reasoning in
  `docs/DECISIONS_LOG.md`'s "Provider decisions" entry.
- **`packages/shared` is now real** (an editable-installed local Python
  package, `aegis-shared`), not just an empty folder per
  `PROJECT_HANDBOOK.md` §4's structure map. Holds exactly one type
  (`SourceLocation`) — deliberately not the SQLAlchemy models, which
  stay independently mirrored in each service instead (see decisions
  log for why).
- **`services/ingestion/src/storage/models.py` is a second, independent
  set of SQLAlchemy models**, not imports from `services/api/src/models/
  db/`. A real architectural fork, explained at length in the decisions
  log — `PROJECT_HANDBOOK.md` §6 Phase 5's file list scopes this phase
  to `services/ingestion/src/` only, and the two services' Celery apps
  already established (Phase 4) the "agree by convention, never by
  sharing Python code" principle this follows.
- **`mypy_path` added to `services/ingestion/pyproject.toml`** — not
  part of any phase's planned file list, needed because `mypy`'s static
  import resolution doesn't follow `setuptools`' modern editable-install
  mechanism the way the real Python interpreter does. Reproduced the
  failure first, then fixed it; see decisions log.
- **`document_classifier.py`'s content-based classification does not
  override or block on a mismatch with the analyst's declared
  `document_type`** — only logged. `docs/architecture.md` §3's decision
  table describes a "manual-review queue" for repeated classification
  failures that doesn't exist as infrastructure yet; a warning log line
  is the honest current substitute.
- Everything from the previous snapshot's deviations list (Phase 4's
  tenant-filtering choice, the multipart form-field shape, `CORSMiddleware`,
  local-disk storage, and earlier phases' items) still stands and wasn't
  touched this phase.

## Immediate Next Step

Phase 5 is done — a real PDF goes in, structured narrative/footnote/table
chunks come out, with a consistent `SourceLocation` in both Qdrant and
Postgres, verified against real infrastructure (not just unit tests).
Next up is **Phase 6: retrieval/generation wired to Chat**
(`PROJECT_HANDBOOK.md` §6) — `services/api/src/core/` doesn't exist yet;
`POST /query`/`POST /query/followup` are still Phase 3's typed stubs.
Phase 6 needs to: implement `bm25_retriever.py`, `dense_retriever.py`,
`hybrid_retriever.py`, `rrf.py`, `reranker.py` (Cohere — already an
agreed dependency in `services/api`), `multi_query.py`, `history_manager.py`,
`answer_generator.py` (needs its own LLM-provider decision — reusing
OpenAI, already added this phase for `services/ingestion`, would avoid a
third vendor, but that's Sam's call, not a default to assume),
`numeric_verifier.py`, `confidence_scorer.py`, and `citation_resolver.py`.
Two concrete carry-overs from this phase, not optional cleanup:
1. **`pip install -e packages/shared` needs to be run in `services/api`'s
   venv too** — `citation_resolver.py` is the first API-side consumer of
   `SourceLocation`, and nothing there installs `aegis-shared` yet.
2. **Dense retrieval must embed queries with `input_type="search_query"`**
   (`services/ingestion/src/embedding/embedder.py`'s `InputType` already
   supports this) — using `"search_document"` for queries would work
   without erroring but measurably hurt retrieval quality, since Cohere's
   v3 embed models are trained with different instruction prefixes per
   `input_type`.

Real ingested data now exists to retrieve against (this phase's live
smoke test left two real, fully-ingested documents in the local Postgres/
Qdrant — one seeded from Phase 4, one this phase's synthetic 10-K test
PDF), so Phase 6 can be verified against real data from the start rather
than needing to re-run ingestion first.
