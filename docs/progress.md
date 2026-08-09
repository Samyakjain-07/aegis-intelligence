# Progress Snapshot — 2026-08-09 (Phase 6)

> Repo state check: real git repository (`git log` shows
> `f80737c chore: initial commit` then `5f78d76 feat: Phase 4 ...`, plus
> an uncommitted Phase 5 + Phase 6 tree at the start of this phase).
> Verified by reading files and running each phase's own commands —
> `mypy` (55 source files, zero errors) and `ruff` (zero errors) inside
> `services/api`'s own venv, all 3 existing unit tests still passing,
> and a **live end-to-end run against real Docker infra and real
> ingested data**, not a synthetic fixture: Postgres/Qdrant/Redis were
> already running and healthy (`docker compose ps`); a real `uvicorn`
> (port 8001) was started against the same Postgres Phase 5 left real
> chunks in — including a genuine downloaded SEC 10-K (Energy Services
> of America Corporation, 284 real chunks across 132 pages, present at
> the repo root, untracked) alongside Phase 5's synthetic Acme Robotics
> test filing (5 chunks, one real 4-row financial table). `POST /query`
> and `POST /query/followup` were exercised directly (`curl`) with real
> Cohere calls (`COHERE_API_KEY` is configured in this environment) for
> embedding, hybrid retrieval, and rerank. This snapshot spans **two**
> live verification passes: the first with no `OPENAI_API_KEY`
> configured (every generation/reformulation/expansion call ran its
> documented no-key fallback path — confirmed working), the second after
> Sam added a real key, exercising the actual LLM-backed path for the
> first time. That second pass caught a real bug on its very first
> LLM-generated answer — `numeric_verifier.py` never scanned text after
> the *last* citation marker, so a model-computed, uncited figure
> ("... $171.3M [1] ... $120.4M [1] ... an increase of $50.9M.") sailed
> through unverified at 0.93 confidence — fixed the same session (see
> `docs/DECISIONS_LOG.md`'s bugfix entry) and re-verified live: the
> identical query now correctly returns confidence 0.23,
> `low_confidence: true`. A numeric question against the Acme table
> (`"What was Acme Robotics data center segment revenue in Q4 2025?"`)
> came back with the exact source figure ($171.3M), a citation resolved
> to `p.3 (table 0)` (reconstructed from Qdrant's payload, not
> re-derived), and confidence 0.90 (no-key pass); a vague,
> un-reformulated follow-up correctly scored low confidence (0.32)
> instead of confidently guessing; a nonsense out-of-corpus query
> correctly scored near-zero (0.02) without needing a hard pre-generation
> block; and, after the key was added, a real history-aware follow-up
> ("What about their logistics segment?") correctly reformulated to "What
> was Acme Robotics logistics segment revenue in Q4 2025?" and answered
> correctly at 0.86 confidence. The frontend was verified (before the key
> was added) with a real headless-browser run (Playwright, driven via a
> one-off scratch script — no `chromium-cli`/project run-skill exists yet
> for this repo) against a real `npm run dev` server and the same live
> API: screenshots confirm a typed question, a rendered answer with live
> citation badges, and the citation side panel showing the correct
> document/page and an extract matching the source table exactly. All
> background processes were stopped after verification; the Postgres/
> Qdrant/Redis containers were left running (untouched, pre-existing).
> Not verified by folder existence at any point.

## Build Order Status

| # | Phase | Status | Reason |
|---|-------|--------|--------|
| 1 | Fix Search crash | **Done** | Unchanged this phase. See `docs/DECISIONS_LOG.md` 2026-08-07 entry. |
| 2 | DB schema | **Done** | Unchanged this phase. See the seven `docs/DECISIONS_LOG.md` entries dated 2026-08-07. |
| 3 | FastAPI skeleton | **Done** | Unchanged this phase. See the `docs/DECISIONS_LOG.md` entry dated 2026-08-08. |
| 4 | Library page vertical slice | **Done** | Unchanged this phase (`citations.py`'s stub got a small, non-functional matching update this phase — see its file inventory row below). |
| 5 | Ingestion pipeline | **Done** | Unchanged this phase. Eleven `docs/DECISIONS_LOG.md` entries dated 2026-08-09. |
| 6 | Retrieval/generation pipeline | **Done** | Real `POST /query`/`POST /query/followup` ([query.py](../services/api/src/api/v1/routes/query.py)) replace Phase 3's stubs, backed by eleven new `services/api/src/core/` modules implementing the full pipeline in `docs/architecture.md` §1 Pipeline B. `frontend/src/app/pages/Chat.tsx` calls the real API. Verified live against real ingested data and through the real browser UI (see snapshot header). Fifteen `docs/DECISIONS_LOG.md` entries dated 2026-08-09, one per pipeline stage/unit. |
| 7 | Remaining pages | **In Progress (UI-only)** | Compare, Admin still hardcoded mock data. Chat.tsx is real as of this phase. |
| 8 | Eval/observability | **Not Started** | `eval/` directory exists, zero files. This phase's live-verified confidence-score behavior (0.90 / 0.32 / 0.02 across three real test questions) is the first informal signal of pipeline quality, not a substitute for Phase 8's actual gold-set eval. |
| 9 | Deployment | **Not Started** | No `Dockerfile`, no prod compose file, no `.github/workflows` files. |

## File Inventory

### services/api/src/core/ — Phase 6 output (new; directory didn't exist before this phase)

| Path | Status | Description |
|------|--------|-------------|
| [types.py](../services/api/src/core/types.py) | Complete (new) | `RankedChunk` (chunk_id + score, pre-hydration), `RetrievedChunk` (fully hydrated, per-stage scores) — the shared value types every other module in this directory agrees on. Not one of `PROJECT_HANDBOOK.md`'s named files; added because five modules needed the same shape. |
| [bm25_retriever.py](../services/api/src/core/bm25_retriever.py) | Complete (new) | `search()` — Postgres full-text search (`to_tsvector`/`websearch_to_tsquery`/`ts_rank_cd`), not a literal Okapi BM25 library — no new dependency needed; see decisions log for the full reasoning. Backed by a new GIN index (below). |
| [dense_retriever.py](../services/api/src/core/dense_retriever.py) | Complete (new) | `embed_query()` (Cohere, `input_type="search_query"`) + `search()` (Qdrant `query_points`). Deliberately does not import `services/ingestion`'s `embedder.py` — services stay decoupled by convention. Also exposes `get_qdrant_client()`, reused by `citation_resolver.py`. |
| [rrf.py](../services/api/src/core/rrf.py) | Complete (new) | `reciprocal_rank_fusion()` — pure function, zero I/O, fuses any number of ranked lists by rank position (not raw score, which isn't comparable across BM25/dense). |
| [hybrid_retriever.py](../services/api/src/core/hybrid_retriever.py) | Complete (new) | `retrieve()` — BM25 + dense in parallel (2-worker `ThreadPoolExecutor`) per query variant, RRF-fused, then one batched Postgres hydration query (joining `Document`/`Company`/`TableData`) for the fused top-N only. Each leg degrades to empty-on-failure rather than raising. |
| [reranker.py](../services/api/src/core/reranker.py) | Complete (new) | `rerank()` — Cohere `rerank-v3.5` over the fused candidates; falls back to the RRF-fused order if `COHERE_API_KEY` is unset or the call fails. |
| [multi_query.py](../services/api/src/core/multi_query.py) | Complete (new) | `expand_query()` — OpenAI-generated alternative phrasings (up to 2), run after history reformulation; falls back to `[query_text]` only on any failure or missing key. |
| [history_manager.py](../services/api/src/core/history_manager.py) | Complete (new) | `reformulate_followup()` — OpenAI rewrite of a follow-up into a self-contained question using the conversation's prior turns (last 6); falls back to the follow-up text unchanged. |
| [answer_generator.py](../services/api/src/core/answer_generator.py) | Complete (new) | `generate_answer()` — grounded OpenAI generation with `[n]`-marker citation requirements in the system prompt; falls back to a zero-synthesis extractive answer (verbatim top-3-chunk content) with no `OPENAI_API_KEY`. Both paths live-verified this phase — the fallback first, then the real LLM path after a key was added (see snapshot header). |
| [numeric_verifier.py](../services/api/src/core/numeric_verifier.py) | Complete (new); one bugfix this phase | `verify_answer()` — deterministic (no LLM) regex/arithmetic extraction of numeric claims per citation marker, checked against that citation's exact source content (full `TableData.raw_table_json` for table chunks, not the truncated `content` summary). Four-way raw/scaled value matching to handle prose-vs-table scale-convention mismatches. Verified live against 58 real numeric claims from a genuine SEC filing table — zero false negatives. **Bugfix (same phase, after the LLM path went live):** text after the last citation marker wasn't scanned at all — an uncited, model-computed derived figure passed through completely unchecked rather than merely unverified. Fixed: trailing text is now scanned and any numeric claim found there is an automatic, unverified failure (`citation_index=0` sentinel). See `docs/DECISIONS_LOG.md`. |
| [confidence_scorer.py](../services/api/src/core/confidence_scorer.py) | Complete (new) | `retrieval_confidence()` (pre-generation signal) + `score_final()` (post-generation: an unverified numeric claim caps confidence hard, regardless of retrieval strength). Live-verified across three real scenarios (0.90 / 0.32 / 0.02). |
| [citation_resolver.py](../services/api/src/core/citation_resolver.py) | Complete (new) | `resolve_source_location()` — cheap Postgres-only reconstruction for narrative/footnote chunks; a Qdrant point lookup (by `chunk_id` = point ID) for table chunks, since `table_cell_ref` only ever lived in Qdrant's payload. `build_snippet()` for the stored citation display text. Live-verified: resolved `p.3 (table 0)` correctly for a real table citation. |

### services/api/src/api/, models/ — Phase 6 changes (existing files)

| Path | Status | Description |
|------|--------|-------------|
| [api/v1/routes/query.py](../services/api/src/api/v1/routes/query.py) | Rewritten | Real `POST /query`/`POST /query/followup`, replacing Phase 3's typed stubs. Shared `_handle_query` runs the full pipeline in order (multi-query → hybrid retrieve → rerank → confidence → generate → verify → confidence (final) → citation resolve), renumbers `[n]` citation markers to line up positionally with the response's `citations` list, and persists `Query`/`Answer`/`Citation` rows. |
| [api/v1/deps.py](../services/api/src/api/v1/deps.py) | Updated | Adds `get_or_create_actor()` — find-or-create for a placeholder `Organization`+`User` (mirrors `documents.py`'s Phase 4 `Company` find-or-create), since Phase 6 is the first phase needing a real, persisted `User` row for `Conversation.user_id` and no seed script/real auth populates one yet. |
| [api/v1/routes/citations.py](../services/api/src/api/v1/routes/citations.py) | Small update | Still a Phase 3 stub (out of Phase 6's scope) — its placeholder `CitationResponse(...)` construction updated with placeholder values for the schema's new required fields (below) so it keeps constructing/type-checking correctly. |
| [models/schemas/citation.py](../services/api/src/models/schemas/citation.py) | Updated | `CitationResponse` gains `document_title`/`document_type`/`ticker`/`page_number`/`fiscal_year`/`fiscal_quarter` — display context sourced from the cited chunk's `Document`/`Company`, not the `Citation` row itself, so `query.py` builds these by hand rather than via `model_validate`. |
| [models/db/__init__.py](../services/api/src/models/db/__init__.py), other `models/db/*.py` | Unchanged | No schema changes to any of the 11 ER-model tables this phase — only a new index (below), no new/altered columns. |

### migrations/ — Phase 6 output (new)

| Path | Status | Description |
|------|--------|-------------|
| [3100d4408cc5_add_document_chunks_content_fts_index.py](../migrations/versions/3100d4408cc5_add_document_chunks_content_fts_index.py) | Complete (new) | Hand-written (not autogenerated — SQLAlchemy's declarative layer has no construct for a functional index) `CREATE INDEX ... USING GIN (to_tsvector('english', content))` on `document_chunks`, backing `bm25_retriever.py`. Applied against the real local Postgres this phase. |

### services/api/ — dependency/config changes

| Path | Status | Description |
|------|--------|-------------|
| [requirements.txt](../services/api/requirements.txt) | Updated | Adds `openai>=1.50` (reusing the Phase 5-approved vendor, now also used for generation/reformulation/expansion — see decisions log) and `-e ../../packages/shared` (this service's first consumer of `SourceLocation`, via `citation_resolver.py` — the concrete carry-over flagged in Phase 5's snapshot). Both installed into the real venv this phase. |
| [pyproject.toml](../services/api/pyproject.toml) | Updated | Adds `[tool.mypy] mypy_path = ["../../packages/shared"]` — same editable-install/mypy gap `services/ingestion` hit in Phase 5, now hit here too since this service imports `aegis_shared` for the first time. |

### frontend/ — Phase 6 output

| Path | Status | Description |
|------|--------|-------------|
| [src/app/lib/api.ts](../frontend/src/app/lib/api.ts) | Updated | Adds `CitationRecord`/`QueryRecord` types (mirroring `query.py`'s Pydantic schemas) and `submitQuery`/`submitFollowupQuery`. |
| [src/app/pages/Chat.tsx](../frontend/src/app/pages/Chat.tsx) | Rewritten | Real conversation state (`messages`, `conversationId`) replacing the hardcoded `MOCK_CITATIONS`/static example Q&A. First message in a thread → `/query`; every subsequent message → `/query/followup`. `[n]` markers in `answer_text` render as clickable badges resolved positionally via `citations[n - 1]` (safe because the backend guarantees contiguous renumbering — see decisions log). Confidence score + low-confidence warning rendered per assistant message. Empty-project state (`activeProject.isEmpty`) untouched — pure frontend/mock concept, no backend `Project` entity exists. |

### Everything else (unchanged this phase, re-verified where noted)

| Area | Status |
|------|--------|
| `services/ingestion` | Unchanged. Not re-run this phase; this phase read the real chunks/tables it wrote in Phase 5 and in ad hoc testing since (see snapshot header). |
| `packages/shared` | Unchanged code-wise. Now installed into **both** services' venvs (`services/ingestion` since Phase 5, `services/api` new this phase). |
| `frontend` (Library, Compare, Admin) | Unchanged. `Compare.tsx`/`Admin.tsx` still mock — Phase 7's scope. |
| `infra/k8s`, `infra/terraform` | Empty. |
| `eval` | Empty. |
| `.github/workflows` | Empty. |
| `docs` | `architecture.md`/`Financial_RAG_Project_Structure.md` unchanged. |
| `data/uploads/` | Gitignored, not touched this phase (no new uploads through the API — this phase queried existing ingested data). |
| Repo root | An untracked real SEC 10-K PDF (`Energy Services of America CORP_September 30, 2025.pdf`) is present, pre-existing at the start of this phase (not created by this phase's work) — its already-ingested chunks were used as this phase's primary live-verification corpus alongside Phase 5's synthetic Acme filing. Not moved, renamed, or committed by this phase. |

## Known Issues / Bugs

**Carried over, unchanged this phase:** the full frontend known-issue
checklist and Phase 4/5 notes from the previous snapshot (unused shadcn
components, disconnected dark-mode tokens, missing aria-labels, no
`GET /documents/{id}/file`, `GET /documents` not tenant-filtered by
design, `POST /documents`'s unguarded find-or-create race, local-disk
storage needing a Phase 9 rework, no dead-letter queue, heuristic
document/table/footnote detection) — see git history for the full table,
none fixed or newly introduced this phase.

**Phase 6-specific notes:**
- **`OPENAI_API_KEY` is now configured** (added partway through this
  phase) — both the no-key fallback paths and the real LLM-backed paths
  for `multi_query.py`/`history_manager.py`/`answer_generator.py` are now
  live-verified (see snapshot header). The LLM path's first real run
  immediately surfaced a genuine bug in `numeric_verifier.py` (uncited
  trailing claims were invisible, not just unverified) — fixed the same
  session; see that file's row above and `docs/DECISIONS_LOG.md`.
- **`get_or_create_actor`'s find-or-create has the same accepted,
  low-probability concurrent-request race** `documents.py`'s `Company`
  find-or-create already accepted in Phase 4 (no `SELECT ... FOR UPDATE`)
  — consistent with existing precedent, not a new gap.
- **Retrieval/rerank/context-size constants
  (`_RETRIEVE_TOP_N=20`, `_RERANK_TOP_N=6`, per-leg `top_k=30`, RRF
  `k=60`, confidence thresholds `0.4`/`0.35`) are all picked by
  inspection**, not tuned against labeled data — Phase 8's eval harness
  is the natural point to revisit every one of these with real numbers
  instead of judgment calls.
- **`numeric_verifier.py`'s match tolerance (`rel_tol=0.02, abs_tol=0.05`)**
  is likewise inspection-calibrated, not validated against a labeled
  mismatch set.
- **No caching of repeated queries or rerank calls** — every request
  pays a full Cohere rerank call even for an identical question asked
  twice. `docs/architecture.md`'s deployment notes flag this as a
  reasonable Phase 9 addition (filings update quarterly, so aggressive
  caching is safe), not addressed here.
- **No streaming** — `answer_generator.py` makes one blocking
  `chat.completions.create` call; the Chat UI shows a static spinner,
  not token-by-token output.
- **`citations.py` (`GET /citations/{id}`) is still a Phase 3 stub** —
  real `Citation`/`Answer`/`Query` rows now exist in Postgres for it to
  actually look up, but that route's real implementation is out of Phase
  6's scope per `PROJECT_HANDBOOK.md`.
- **No `tsconfig.json` for the frontend yet** (flagged since Phase 1) —
  `Chat.tsx`'s new TypeScript was verified via `vite build` (real
  transpilation/bundling, catches unresolved imports and syntax errors)
  and a live browser run, not `tsc --noEmit`.
- **No automated integration test for the query pipeline in CI** — this
  phase's verification was live and manual (direct API calls + a
  Playwright-driven browser session), matching Phase 5's precedent; a
  real `tests/integration/test_query_endpoint.py` (named in
  `Financial_RAG_Project_Structure.md`'s original plan) doesn't exist
  yet.

**Grep for TODO/FIXME/XXX/NotImplementedError/bare `pass`:** No matches
under `services/api/src/core` or the modified files (checked as part of
this phase).

## Deviations From the Original Plan

- **`bm25_retriever.py` uses Postgres full-text search, not a literal
  BM25 implementation** — no new dependency needed (Postgres is already
  the agreed relational store); `rank_bm25`/Elasticsearch/OpenSearch
  would each have been a new external dependency requiring a check-in
  per `CLAUDE.md` §4. Full reasoning in `docs/DECISIONS_LOG.md`.
- **`openai>=1.50` added to `services/api/requirements.txt`** — not
  treated as a fresh "new dependency" check-in since the vendor itself
  was already approved project-wide in Phase 5 (asked of Sam directly
  this phase anyway, for which *use* — generation vs. a new vendor —
  per Phase 5's explicit "this entry doesn't presume [Phase 6] has to be
  OpenAI too" note). See decisions log.
- **`core/types.py` was added beyond `PROJECT_HANDBOOK.md`'s named file
  list** — a small shared-value-types module (`RankedChunk`,
  `RetrievedChunk`) five other named modules needed to agree on; not
  business logic, the same spirit as `packages/shared`'s `SourceLocation`.
- **`CitationResponse` gained six display-only fields not in the
  original Phase 3 schema** — needed so the Chat UI's citation panel can
  render ticker/document/page context without a second round-trip per
  citation; additive, not a breaking change to the schema's original
  fields.
- **`get_or_create_actor` (a real, if placeholder, `User`/`Organization`
  find-or-create) was added to `deps.py`**, not part of any phase's
  planned file list — a real, previously-undiscovered gap (no seed
  script or real auth ever populated `organizations`/`users`), resolved
  by extending the exact pattern Phase 4 already established for
  `Company`, not a new convention.
- **`numeric_verifier.py`'s citation-marker window logic changed mid-phase**
  from what was originally shipped and decisions-logged (only text
  *preceding* a `[n]` marker was ever scanned) to also scanning text
  *after* the last marker as automatic unverified failures — not part of
  the original design, discovered live once a real `OPENAI_API_KEY` was
  added and a real model produced an uncited trailing claim. See the
  dedicated bugfix entry in `docs/DECISIONS_LOG.md`.
- Everything from the previous snapshot's deviations list (Phase 4's
  tenant-filtering/shared-corpus choice, Phase 5's provider decisions and
  independent storage models) still stands and wasn't touched this phase.

## Immediate Next Step

Phase 6 is done — a real question in the Chat UI now produces a grounded
answer with citations that resolve to a real page/table location, live-
verified against both a synthetic filing and a genuine downloaded SEC
10-K, with confidence scoring that behaves sensibly across a strong
match, a weak match, a nonsense query, and (after a real `OPENAI_API_KEY`
was added and immediately caught a real numeric-verification bug, since
fixed) genuine LLM-backed generation and follow-up reformulation. Next up
is **Phase 7: remaining pages** (`PROJECT_HANDBOOK.md` §6) — `Compare.tsx`
and `Admin.tsx` still render `MOCK_METRICS`/inline mock arrays; Phase 7
needs real endpoints for cross-quarter metric comparison and the Admin
analytics/flagged-answers views (reading from the `Answer`/`Citation`/
`EvalResult` tables Phase 6 now actually populates).

One concrete carry-over from this phase, not optional cleanup:
**Phase 8's eval harness should revisit every inspection-calibrated
constant** introduced this phase (`_RETRIEVE_TOP_N`, `_RERANK_TOP_N`,
RRF's `k`, `numeric_verifier.py`'s match tolerance, both confidence
thresholds) against real gold-set numbers instead of judgment calls made
without eval data — and specifically re-check `numeric_verifier.py`'s
now-strict "an uncited claim is always unverified" rule against real
model outputs at scale, since it was added from a single live example,
not a labeled set.
