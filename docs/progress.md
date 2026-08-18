# Progress Snapshot — 2026-08-18 (Phase 8)

> Repo state check: real git repository, `main` branch. Working tree was
> clean at the start of this phase except for Phase 7's own output, which
> this phase committed first (`a784f73 feat: Phase 7 - Compare/Admin wired
> to real data`) before starting Phase 8's own work. This phase's Phase 8
> changes are uncommitted at the time of this snapshot. Verified by
> reading every changed/new file, not by folder existence: `mypy` (61
> source files in `services/api/src`, zero errors), `ruff` (zero errors,
> `services/api/` and `eval/ragas_runner.py` both checked), all 3 existing
> unit tests still passing, and a **live end-to-end eval run** — Docker
> Desktop was started fresh this phase (not running at session start),
> `docker compose up -d` brought up the same Postgres/Qdrant/Redis
> containers (and their existing volumes) Phases 5–7 already populated, a
> real `uvicorn` was started (port 8000), and `python eval/ragas_runner.py`
> was run three times against it with real `COHERE_API_KEY`/
> `OPENAI_API_KEY` already present in `.env`: once producing deterministic-
> fallback scores, once (after fixing a real RAGAS/`langchain-community`
> incompatibility found by that first run) producing real RAGAS LLM-judged
> `faithfulness`/`context_precision` scores, and once confirming
> `--fail-under` actually gates (exit 1 at `--fail-under 0.9`, exit 0 at
> the default). A genuine data-quality bug was also found and fixed live
> this phase (see Known Issues). All 24 real `EvalResult` rows these runs
> produced are still in Postgres. Docker Desktop's backend crashed
> mid-phase from an accidental `taskkill` on one of its own proxy
> processes (not a code issue) and was restarted; Postgres/Qdrant/Redis
> data was confirmed intact afterward via a direct query, and the unit
> test suite was re-run clean post-restart. All background processes this
> phase started (one `uvicorn`, several `pip install`/`pytest`/`mypy`/
> `ruff` runs) were stopped afterward; Docker containers were left running,
> matching every prior phase's precedent. Not verified by folder existence
> at any point.

## Build Order Status

| # | Phase | Status | Reason |
|---|-------|--------|--------|
| 1 | Fix Search crash | **Done** | Unchanged this phase. See `docs/DECISIONS_LOG.md` 2026-08-07 entry. |
| 2 | DB schema | **Done** | Unchanged this phase (no migration, no ORM model touched). See the seven `docs/DECISIONS_LOG.md` entries dated 2026-08-07. |
| 3 | FastAPI skeleton | **Done** | Unchanged this phase. See the `docs/DECISIONS_LOG.md` entry dated 2026-08-08. |
| 4 | Library page vertical slice | **Done** | Unchanged this phase. |
| 5 | Ingestion pipeline | **Done** | Unchanged this phase. |
| 6 | Retrieval/generation pipeline | **Done** | Unchanged this phase except additive, behavior-preserving instrumentation (see Phase 8 row) — no pipeline logic touched. |
| 7 | Remaining pages (Compare, Admin) | **Done** | Committed this phase as `a784f73` (was uncommitted at the start of this session). Unchanged otherwise. |
| 8 | Eval/observability | **Done** | Gold Q&A set ([eval_dataset.jsonl](../services/api/tests/eval/eval_dataset.jsonl), 12 items), eval harness ([ragas_runner.py](../eval/ragas_runner.py)), LangSmith tracing hooks + latency/hit-rate/groundedness metrics ([tracing.py](../services/api/src/observability/tracing.py), [metrics.py](../services/api/src/observability/metrics.py)), and a CI eval-regression workflow ([eval-regression.yml](../.github/workflows/eval-regression.yml)) all exist and are live-verified against real ingested data and a real running API — not just present. Six `docs/DECISIONS_LOG.md` entries dated 2026-08-18. One real retrieval-quality gap surfaced by the live run (see Known Issues), left open on purpose as this phase's actual eval finding, not silently fixed. |
| 9 | Deployment | **Not Started** | No `Dockerfile`, no prod compose file. `.github/workflows/eval-regression.yml` exists (Phase 8, not Phase 9's `ci.yml`/`cd-staging.yml`) but has never run in real GitHub Actions — see Known Issues. |

## File Inventory

### eval/ — Phase 8 output (new)

| Path | Status | Description |
|------|--------|-------------|
| [ragas_runner.py](../eval/ragas_runner.py) | Complete (new) | Runs `services/api/tests/eval/eval_dataset.jsonl`'s gold Q&A set against a real, running `POST /api/v1/query` over HTTP (not a direct `core/` import — see its own docstring for why). Scores each item two ways: real RAGAS LLM-judged `faithfulness`/`context_precision` when `OPENAI_API_KEY` + the `ragas`/`langchain-openai` packages are available, a deterministic ticker-match/`confidence_score` fallback otherwise — both modes live-verified this phase, not just written. Writes one `EvalResult` row per scored item (upserted on `query_id`), prints a summary, exits non-zero on `--fail-under`. |

### services/api/tests/eval/ — Phase 8 output (new)

| Path | Status | Description |
|------|--------|-------------|
| [eval_dataset.jsonl](../services/api/tests/eval/eval_dataset.jsonl) | Complete (new) | 12 gold Q&A items: 4 numeric + 2 narrative against Acme Robotics' real extracted table/narrative (ticker `ACME`), 3 numeric + 2 narrative against Energy Services of America's real narrative-only 10-K (ticker `ESOA`, exercising `numeric_verifier.py`'s non-table code path for the first time against real data), and 1 deliberate negative control (a company never ingested, correct answer is an honest decline). Every ground-truth figure/fact was independently verified by reading the two real source PDFs directly, not reconstructed from prior phases' own docs. |

### services/api/src/observability/ — Phase 8 output (new)

| Path | Status | Description |
|------|--------|-------------|
| [tracing.py](../services/api/src/observability/tracing.py) | Complete (new) | `traced_stage()` decorator, applied to 8 real `core/` pipeline functions (`multi_query.expand_query`, `hybrid_retriever.retrieve`, `reranker.rerank`, `answer_generator.generate_answer`, `numeric_verifier.verify_answer`, `confidence_scorer.retrieval_confidence`/`score_final`, `citation_resolver.resolve_source_location`, `history_manager.reformulate_followup`). A true no-op (function returned completely unwrapped) unless `LANGCHAIN_TRACING_V2`/`LANGCHAIN_API_KEY` are set and `langsmith` is installed — live-confirmed disabled (no key supplied to this session) throughout this phase's real query runs, all of which completed with unchanged behavior. |
| [metrics.py](../services/api/src/observability/metrics.py) | Complete (new) | `StageTimer` (wired into `query.py`'s `_handle_query`, live-verified — real per-stage millisecond timings logged on every real request this phase's eval runs made) plus `citation_hit_rate`/`deterministic_groundedness`, the two pure functions `eval/ragas_runner.py`'s deterministic fallback and the live pipeline share — one definition of each metric. |

### Existing files changed this phase

| Path | Status | Description |
|------|--------|-------------|
| [api/v1/routes/query.py](../services/api/src/api/v1/routes/query.py) | Updated | `_handle_query` now times each pipeline stage via `StageTimer` and logs one structured summary line per request. No pipeline logic changed. |
| [core/{multi_query,hybrid_retriever,reranker,answer_generator,numeric_verifier,confidence_scorer,citation_resolver,history_manager}.py](../services/api/src/core/) | Updated | Each gains one import + one `@traced_stage(...)` decorator line on its real pipeline-entry function. No logic changed — verified by mypy/ruff/the existing unit-test suite all staying clean, and by this phase's live eval run producing the same kind of real, correctly-cited answers Phase 6/7's own live runs did. |
| [requirements.txt](../services/api/requirements.txt) | Updated | Adds `ragas`, `langchain-openai`, `datasets`, `langsmith` (Phase 8's named stack picks, `CLAUDE.md` §3), plus a pinned `langchain-community==0.3.31` + `dataclasses-json` — a real incompatibility between `ragas==0.4.3` and `langchain-community`'s current (0.4.x) release, found and fixed via a live `pip install` + eval run this phase (see `docs/DECISIONS_LOG.md`), not a guessed version floor. |
| [.env.example](../.env.example) | Updated | Documents `LANGCHAIN_TRACING_V2`/`LANGCHAIN_API_KEY`/`LANGCHAIN_PROJECT` and `EVAL_API_URL`/`EVAL_FAIL_UNDER`, all optional, matching this file's existing "placeholders only, real values never committed" convention. |

### .github/workflows/ — Phase 8 output (new)

| Path | Status | Description |
|------|--------|-------------|
| [eval-regression.yml](../.github/workflows/eval-regression.yml) | Complete (new), **not yet run in real GitHub Actions** | Scheduled (daily) + manually-dispatchable workflow provisioning Postgres/Qdrant/Redis, running migrations, starting a real `uvicorn`, and running `eval/ragas_runner.py` with a `--fail-under` gate. Its own header comment honestly documents the one real limitation: a GitHub-hosted ephemeral runner has no persistent ingested corpus, so the default path runs in report-only mode until `eval-api-url`/`EVAL_API_URL` points at a real, already-ingested environment. Never actually triggered in GitHub Actions this phase — doing so needs a push/PR and repo secrets this session cannot configure or observe. |

### Data fix (not a code change)

| What | Status | Description |
|------|--------|-------------|
| `companies` row for Energy Services of America | Fixed | Was seeded with `ticker='CORP'`/`name='CORP'` (a mistyped placeholder from earlier manual upload testing), which `eval_dataset.jsonl`'s five ESOA gold items would have silently failed against. Corrected to `ticker='ESOA'`/`name='Energy Services of America Corporation'` via a single `UPDATE`, verified against the source PDF's own cover page. A data fix, not a schema change — outside `CLAUDE.md` §4's migration-boundary concern, but flagged explicitly per that section's spirit. See `docs/DECISIONS_LOG.md`'s `eval/ragas_runner.py` entry for the full story. |

### Everything else (unchanged this phase, re-verified where noted)

| Area | Status |
|------|--------|
| `services/ingestion` | Unchanged. Not re-run this phase. |
| `packages/shared` | Unchanged. |
| `services/api/src/models/db/*` | Unchanged. No migration this phase. |
| `frontend` | Unchanged. |
| `infra/k8s`, `infra/terraform` | Empty. |
| `docs/architecture.md` | Unchanged. |
| `data/uploads/` | Gitignored, not touched this phase (still holds the same two real fixture PDFs this phase's gold set reads directly). |

## Known Issues / Bugs

**Carried over, unchanged this phase:** the full frontend known-issue
checklist and Phase 4/5/6/7 notes from the previous snapshot (unused
shadcn components, disconnected dark-mode tokens, missing aria-labels, no
`GET /documents/{id}/file`, `GET /documents` not tenant-filtered by
design, `POST /documents`'s unguarded find-or-create race, local-disk
storage needing a Phase 9 rework, no dead-letter queue, heuristic
document/table/footnote detection, no streaming, no query/rerank caching,
no `tsconfig.json`, no automated integration tests in CI, `Layout.tsx`'s
`MOCK_PROJECTS`) — see git history for the full table, none fixed or
newly introduced this phase.

**Phase 8-specific notes:**
- **A real, open retrieval-quality finding, left unfixed on purpose:**
  the live eval run's two keyword-check failures (`eval-007`: "What was
  Energy Services of America's total revenue for fiscal year 2025?";
  `eval-011`: "On which stock exchange does ESOA's common stock trade,
  and under what ticker symbol?") are genuine retrieval misses against
  ESOA's real, table-less, 284-chunk document — both real live answers
  are honest "the context does not provide..." declines with zero
  citations (confirmed by hand via `curl`), not a harness bug. This is
  exactly the kind of specific, actionable signal `CLAUDE.md` §1's eval
  mandate exists to produce, and chasing it (retrieval-parameter tuning
  against real eval data) is explicitly Phase 8's own **next** step per
  `PROJECT_HANDBOOK.md` §6, not something to silently patch inside this
  pass.
- **Every inspection-calibrated retrieval/confidence constant is still
  unvalidated against real eval data** — `_RETRIEVE_TOP_N`/`_RERANK_TOP_N`
  (`query.py`), RRF's `k`, `LOW_CONFIDENCE_THRESHOLD`/
  `_UNVERIFIED_CLAIM_CEILING` (`confidence_scorer.py`), `numeric_verifier.
  py`'s match tolerance. Phase 8's real scores (mean groundedness 0.549,
  mean precision 0.667, RAGAS-judged) now exist as the first real baseline
  to tune any of these against — flagged since Phase 6/7 as "Phase 8's
  job," now genuinely actionable rather than aspirational.
- **`eval-regression.yml` has never run in real GitHub Actions** — see
  its own file-inventory row above and its header comment for the full,
  honestly-stated limitation (no persistent ingested corpus on a
  GitHub-hosted ephemeral runner).
- **`LANGCHAIN_API_KEY` was never supplied to this session** (by design —
  real secrets aren't typed into a session, per `.env.example`'s own
  convention) — `tracing.py`'s disabled/no-op path is live-verified,
  its enabled path (a real trace appearing in the LangSmith UI) is not.
- **A second, separate pre-existing data-quality oddity was found but
  deliberately left untouched:** a `Company` row with `ticker='AI'`
  backs an unrelated health-NLP PDF that was ingested and misclassified
  as `FORM_10K` at some point before this phase (first visible in Phase
  7's Admin "Most-Cited Companies" live-test screenshot, `docs/
  DECISIONS_LOG.md`'s "ACME 13, CORP 9, AI 1" mention). Not referenced by
  this phase's gold set, and correcting/removing it would alter data
  Phase 7's own live-verification already depended on — flagged for Sam,
  not silently fixed alongside the `CORP`→`ESOA` correction above.

**Grep for `TODO`/`FIXME`/`XXX`/`NotImplementedError`/bare `pass`:** No
matches in any file this phase added or changed.

## Deviations From the Original Plan

- **The `ragas`/`langchain-community` version pin** (`services/api/
  requirements.txt`) is a real, discovered-live necessity, not a
  precautionary guess — see the `eval/ragas_runner.py` decisions-log
  entry for the full incompatibility and fix.
- **`langchain-community`, `dataclasses-json`, `langchain-openai`,
  `datasets`, `langsmith` were added as transitive/direct dependencies of
  RAGAS and LangSmith** (both already named in `CLAUDE.md` §3's agreed
  stack) — not a new stack choice, flagged the same way Phase 6/7's own
  small additive dependencies were.
- Everything from the previous snapshot's deviations list (Phase 4's
  tenant-filtering/shared-corpus choice, Phase 5's provider decisions,
  Phase 6's `CitationResponse`/`get_or_create_actor` additions and the
  `numeric_verifier.py` bugfix, Phase 7's Compare/Admin scope pivots)
  still stands and wasn't touched this phase.

## Immediate Next Step

Phase 8 is done and live-verified — real gold Q&A set, real eval harness,
real per-request tracing/metrics instrumentation, a real CI workflow file
(not yet exercised in GitHub Actions itself), and a real first eval
baseline: **mean retrieval_precision 0.667, mean groundedness_score
0.549, keyword-check pass rate 10/12**, RAGAS-scored against real
ingested data.

Two concrete, non-optional carry-overs from this phase, not blocking but
real:

1. **The `eval-007`/`eval-011` retrieval miss against ESOA is worth a
   real investigation** — likely candidates: `agentic_chunker.py`'s
   section boundaries splitting the relevant sentences awkwardly across
   chunks, or `_RETRIEVE_TOP_N`/`_RERANK_TOP_N` being too narrow for a
   284-chunk table-less document. This is precisely the kind of finding
   `PROJECT_HANDBOOK.md` §6 Phase 8 names as the reason to revisit every
   inspection-calibrated constant — now there's a real number to tune
   against instead of judgment calls.
2. **`eval-regression.yml` needs a real GitHub Actions run** to move from
   "written and locally sound" to "actually gating" — requires either
   `COHERE_API_KEY`/`OPENAI_API_KEY` repo secrets and a fixture-seeding
   step (a real, scoped Phase 9 decision, per that workflow's own header
   comment) or a self-hosted runner pointed at Sam's already-ingested
   local Docker infra.

Otherwise, per `PROJECT_HANDBOOK.md`'s nine-phase plan, **Phase 9:
Deployment** (`services/api`/`services/ingestion` Dockerfiles,
`docker-compose.prod.yml`, Terraform scaffolding, `ci.yml`/
`cd-staging.yml`) is next.
