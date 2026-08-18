# Progress Snapshot — 2026-08-09 (Phase 7)

> Repo state check: real git repository, `main` branch, working tree
> otherwise clean at the start of this phase (`dbebd75 feat: Phase 6 -
> retrieval/generation pipeline wired to Chat` was the tip commit). This
> phase's changes are uncommitted at the time of this snapshot. Verified
> by reading every changed/new file, not by folder existence: `mypy` (58
> source files in `services/api/src`, zero errors), `ruff` (zero errors),
> all 3 existing unit tests still passing, and a **live end-to-end run**
> against real Docker infra and the same real ingested data Phases 5/6
> left in Postgres/Qdrant (Postgres/Qdrant/Redis were already running and
> healthy — `docker compose ps`). A real `uvicorn` (port 8001) was
> started and `GET /admin/analytics`, `GET /admin/flagged-answers`, and
> `GET /compare/metric` were exercised directly via `curl` against real
> data (11 real `Query`/`Answer` rows from Phases 5-6's testing, 3 of them
> genuinely low-confidence and therefore genuinely flagged; a real
> `TableData` row for Acme Robotics' synthetic 10-K). The frontend was
> then verified with a real headless-browser run (Playwright, driven via
> a one-off scratch script — still no `chromium-cli`/project run-skill
> exists for this repo) against a real `npm run dev` server (an existing,
> pre-running Vite dev server on port 5173 was reused rather than
> spinning up a redundant one — its origin was already in `main.py`'s
> default CORS allow-list) and the same live API: screenshots confirm the
> Compare page's ticker/metric picker returning real quarterly values
> with a working citation-panel link, and the Admin dashboard's KPI
> cards, 7-day query-volume chart, most-cited-companies panel, and
> flagged-answers table all rendering real numbers, with zero browser
> console errors. All background processes this phase started (one
> `uvicorn`, one redundant `vite` instance) were stopped afterward,
> without touching the pre-existing dev server or the Postgres/Qdrant/
> Redis containers. Not verified by folder existence at any point.

## Build Order Status

| # | Phase | Status | Reason |
|---|-------|--------|--------|
| 1 | Fix Search crash | **Done** | Unchanged this phase. See `docs/DECISIONS_LOG.md` 2026-08-07 entry. |
| 2 | DB schema | **Done** | Unchanged this phase (no migration, no ORM model touched — Phase 7 only added Pydantic schemas and read-only queries). See the seven `docs/DECISIONS_LOG.md` entries dated 2026-08-07. |
| 3 | FastAPI skeleton | **Done** | Unchanged this phase. See the `docs/DECISIONS_LOG.md` entry dated 2026-08-08. |
| 4 | Library page vertical slice | **Done** | Unchanged this phase. |
| 5 | Ingestion pipeline | **Done** | Unchanged this phase. |
| 6 | Retrieval/generation pipeline | **Done** | Unchanged this phase. |
| 7 | Remaining pages (Compare, Admin) | **Done** | Real `GET /compare/metric` ([compare.py](../services/api/src/api/v1/routes/compare.py)) and rewritten `GET /admin/analytics`/`GET /admin/flagged-answers` ([admin.py](../services/api/src/api/v1/routes/admin.py)) replace every placeholder from Phase 3/the frontend mocks. `Compare.tsx`/`Admin.tsx` call them for real. Zero `MOCK_` references remain under `frontend/src/app` **except** `Layout.tsx`'s `MOCK_PROJECTS` — out of this phase's named scope and with no backing ER entity; see Known Issues. Four `docs/DECISIONS_LOG.md` entries dated 2026-08-09 (two backend, two frontend), live-verified against real Postgres data and a real browser session. |
| 8 | Eval/observability | **Not Started** | `eval/` directory exists, zero files. |
| 9 | Deployment | **Not Started** | No `Dockerfile`, no prod compose file, no `.github/workflows` files. |

## File Inventory

### services/api/src/ — Phase 7 output (new files)

| Path | Status | Description |
|------|--------|-------------|
| [core/metric_comparator.py](../services/api/src/core/metric_comparator.py) | Complete (new) | `find_metric_across_documents()` — for a ticker + free-text metric label, walks every `COMPLETED` `Document` for that `Company` and returns the first table row per document (by page, then chunk order, then row order) whose first cell contains the metric as a case-insensitive substring. Reuses `citation_resolver.resolve_source_location` (Phase 6) for `exact_location`, so Compare's citations resolve identically to Chat's. Not one of `PROJECT_HANDBOOK.md`'s named files — added the same way `core/types.py` was in Phase 6, a focused module the route needed and no existing one covered. |
| [api/v1/routes/compare.py](../services/api/src/api/v1/routes/compare.py) | Complete (new) | `GET /compare/metric` — real implementation of `docs/architecture.md` §8 UC5 ("Compare metrics across quarters"), replacing the fact that no Compare route existed at all before this phase. 404s on an unknown ticker; 200 with an empty `periods` list on a known ticker with no metric match — two genuinely different outcomes, not collapsed into one. |
| [models/schemas/compare.py](../services/api/src/models/schemas/compare.py) | Complete (new) | `CompareMetricResponse`/`CompareMetricPeriodResponse` — `headers`/`values` travel as parallel lists (never a flattened string), matching `TableData.raw_table_json`'s own shape. |

### services/api/src/ — Phase 7 changes (existing files)

| Path | Status | Description |
|------|--------|-------------|
| [api/v1/routes/admin.py](../services/api/src/api/v1/routes/admin.py) | Rewritten | `GET /admin/analytics` and `GET /admin/flagged-answers` now compute real KPI counters (total/indexed documents, total conversations/queries, average confidence, flagged count + rate, active analysts), a zero-filled 7-day query-volume-vs-flagged series, a most-cited-companies panel (`GROUP BY` over real `Citation` rows), and the flagged-answers table — all from real `Document`/`Conversation`/`Query`/`Answer`/`Citation`/`EvalResult` rows, replacing Phase 3's all-zero/empty placeholders. "Flagged" = `Answer.confidence_score < confidence_scorer.LOW_CONFIDENCE_THRESHOLD` OR `EvalResult.flagged_by_human` (imported threshold, not a re-declared magic number). `Conversation`/`Query`/`Answer`/`EvalResult` counts are scoped by `tenant.org_id`; `Document`/`Company` counts are not (mirrors Phase 4's `documents.py` precedent). |
| [models/schemas/admin.py](../services/api/src/models/schemas/admin.py) | Rewritten | `AdminAnalyticsResponse` gains `indexed_document_count`, `low_confidence_rate`, `active_analyst_count`, `query_volume_last_7_days` (`QueryVolumeDayResponse`), `top_cited_tickers` (`TickerCitationCountResponse`). `FlaggedAnswerResponse` gains `conversation_id`, `user_email`, `flag_reason`, `generated_at`. |
| [main.py](../services/api/src/main.py) | Updated | Registers `compare.router` alongside the existing v1 routers. |

### frontend/ — Phase 7 output

| Path | Status | Description |
|------|--------|-------------|
| [src/app/lib/api.ts](../frontend/src/app/lib/api.ts) | Updated | Adds `compareMetric`/`CompareMetricResponse`/`CompareMetricPeriod` and `fetchAdminAnalytics`/`AdminAnalytics`/`fetchFlaggedAnswers`/`FlaggedAnswer` — mirroring the new backend schemas the same way Phase 6's additions mirrored `query.py`'s. |
| [src/app/pages/Compare.tsx](../frontend/src/app/pages/Compare.tsx) | Rewritten | `MOCK_METRICS` gone. Real ticker dropdown (derived from `fetchDocuments()`'s `status === 'completed'` rows — no new `GET /companies` endpoint added, matching Phase 4's documented gap), a free-text metric input with quick-select suggestion chips, and a results table rendering each matched period's own `headers`/`values` (not forced into a fixed Q1-Q4 grid, since real per-document tables can have different column structures). Clicking a result's source location reuses `Layout.tsx`'s existing global citation side panel. |
| [src/app/pages/Admin.tsx](../frontend/src/app/pages/Admin.tsx) | Rewritten | `MOCK_CHART_DATA`, `FLAGGED_QUERIES`, and the inline "Top Query Topics" array are gone. KPI cards, the query-volume chart, a "Most-Cited Companies" panel (real citation data, replacing the topic-modeling mock that would have needed a new, unapproved dependency), and the flagged-answers table all call the real Admin backend via `Promise.allSettled` (one endpoint failing doesn't blank the other panel). |

### Everything else (unchanged this phase, re-verified where noted)

| Area | Status |
|------|--------|
| `services/ingestion` | Unchanged. Not re-run this phase. |
| `packages/shared` | Unchanged. |
| `services/api/src/models/db/*`, `services/api/src/core/{bm25,dense,hybrid}_retriever,rrf,reranker,multi_query,history_manager,answer_generator,numeric_verifier,confidence_scorer,citation_resolver}.py` | Unchanged. No schema/migration changes this phase — Phase 7 is entirely new read-only routes + Pydantic schemas over existing tables. |
| `frontend` (Chat, Library) | Unchanged. |
| `infra/k8s`, `infra/terraform` | Empty. |
| `eval` | Empty. |
| `.github/workflows` | Empty. |
| `docs/architecture.md` | Unchanged. |
| `data/uploads/` | Gitignored, not touched this phase. |

## Known Issues / Bugs

**Carried over, unchanged this phase:** the full frontend known-issue
checklist and Phase 4/5/6 notes from the previous snapshot (unused
shadcn components, disconnected dark-mode tokens, missing aria-labels, no
`GET /documents/{id}/file`, `GET /documents` not tenant-filtered by
design, `POST /documents`'s unguarded find-or-create race, local-disk
storage needing a Phase 9 rework, no dead-letter queue, heuristic
document/table/footnote detection, no streaming, no query/rerank caching,
no `tsconfig.json`, no automated integration tests in CI, every
inspection-calibrated retrieval/confidence constant still unvalidated
against real eval data) — see git history for the full table, none fixed
or newly introduced this phase.

**Phase 7-specific notes:**
- **`Layout.tsx`'s `MOCK_PROJECTS` is the one remaining `MOCK_` reference
  under `frontend/src/app`.** Deliberately not touched: `Layout.tsx` was
  not in Phase 7's named file list (`Compare.tsx`/`Admin.tsx` only), and
  there is no `Project` entity anywhere in `docs/architecture.md` §7's ER
  model to wire it to — inventing one would be a real ER-model deviation
  (`CLAUDE.md` §4: "Deviate from the ER model... " requires asking
  first), not something to do silently under a "remove all mocks" phase
  whose own prompt only named two other files. Flagged explicitly for
  Sam rather than left implicit; this was also already true and
  documented at the end of Phase 6's snapshot.
- **The two real ingested-data fixtures don't exercise true
  multi-document "compare across quarters" end to end** (see the Compare
  backend's `docs/DECISIONS_LOG.md` entry's tradeoffs note in full): Acme
  Robotics' one synthetic 10-K already has all four quarters inside a
  single table (segment-rows x quarter-columns), and the real Energy
  Services of America 10-K has zero extracted tables at all (a
  pre-existing Phase 5 `camelot`/`layout_segmenter.py` gap, out of this
  phase's scope). `GET /compare/metric`'s mechanism is fully live-
  verified (row matching, real values, real citation resolution via
  Qdrant) against `ticker=ACME, metric="Data Center"` — what's *not* yet
  demonstrated live is the "same metric, several separate filings"
  scenario the feature is ultimately for, since no company in the current
  dev data has more than one filing with an extracted table. This will
  resolve itself the moment a second real quarterly filing (with tables
  camelot can actually extract) is ingested for the same company — no
  code change implied.
- **No admin-only authorization on `/admin/*` or `/compare/*`** —
  `tenant.role` is always `None` until real auth exists (`deps.py`,
  unchanged since Phase 3); anyone can currently hit these routes, same
  as every other route in the API today.
- **`FlaggedAnswerResponse` has no "Reviewed" vs. "Pending Review"
  workflow state** — no such column exists in the ER model
  (`EvalResult.flagged_by_human` is a flag, not a workflow status), and
  adding one wasn't asked for by this phase's scope. The frontend shows
  each row's real `confidence_score` instead of a fabricated status
  badge.
- **`active_analyst_count` and `total_conversations` will read `1` on
  this dev machine** for as long as `get_or_create_actor`'s single
  placeholder `User` (`deps.py`, since Phase 6) is the only one any
  request ever resolves to — real, not fake, given the current auth
  state, but worth knowing before reading too much into the number.

**Grep for `TODO`/`FIXME`/`XXX`/`NotImplementedError`/bare `pass`:** No
matches in any file this phase added or changed (checked as part of this
phase). **Grep for `MOCK_` under `frontend/src/app`:** one match,
`Layout.tsx`'s `MOCK_PROJECTS` — see above.

## Deviations From the Original Plan

- **"Top Query Topics" (the Admin mock) became "Most-Cited Companies"
  (real data)** — topic modeling would need a new dependency (an
  embedding-clustering library or a dedicated LLM call) not in the agreed
  stack (`CLAUDE.md` §3); which company's filings actually got cited
  across real answers is genuine, queryable data the schema already
  supports. A deliberate, flagged scope pivot, not a silent swap.
- **No new `GET /companies` endpoint** — the Compare page's ticker
  dropdown derives its options from the existing `GET /documents`
  response client-side instead. `PROJECT_HANDBOOK.md`'s Phase 7 prompt
  only asked for the metric-comparison endpoint itself; adding a second
  new route wasn't necessary to satisfy it.
- **`core/metric_comparator.py` was added beyond `PROJECT_HANDBOOK.md`'s
  named file list** — same spirit as Phase 6's `core/types.py`: a small,
  focused module the named route needed, not business logic invented
  beyond scope.
- Everything from the previous snapshot's deviations list (Phase 4's
  tenant-filtering/shared-corpus choice, Phase 5's provider decisions,
  Phase 6's `CitationResponse`/`get_or_create_actor` additions and the
  `numeric_verifier.py` bugfix) still stands and wasn't touched this
  phase.

## Immediate Next Step

Phase 7 is done — `Compare.tsx` and `Admin.tsx` both call real endpoints
now, and (`Layout.tsx`'s out-of-scope `MOCK_PROJECTS` aside — see Known
Issues) zero mock data remains anywhere under `frontend/src/app`. Both
pages are live-verified against real Postgres data through a real browser
session with zero console errors. Next up is **Phase 8: eval +
observability** (`PROJECT_HANDBOOK.md` §6) — a gold Q&A dataset, a RAGAS/
DeepEval runner producing real retrieval-precision and groundedness
numbers against the live query pipeline, LangSmith/Phoenix tracing hooks,
and a CI eval-regression gate. This is also the natural point to revisit
every inspection-calibrated constant flagged since Phase 6
(`_RETRIEVE_TOP_N`, `_RERANK_TOP_N`, RRF's `k`, both confidence
thresholds, `numeric_verifier.py`'s match tolerance) against real gold-set
numbers instead of judgment calls — and, now that Phase 7 actually reads
`EvalResult.flagged_by_human` in two live endpoints, Phase 8's harness
writing real `EvalResult` rows will make the "flagged by human reviewer"
path in `admin.py`'s `_flagged_condition()` exercised for the first time,
not just present-but-dormant.

One concrete carry-over, not optional cleanup: **ingest a second real
quarterly filing for a company that already has one**, once Phase 8's
work or further manual testing calls for it — that's what turns
`GET /compare/metric`'s already-live-verified single-document mechanism
into a live-verified true multi-quarter comparison, the scenario the
feature exists for.
