# Progress Snapshot — 2026-08-08 (Phase 4)

> Repo state check: real git repository (`git log` shows one prior commit,
> `f80737c chore: initial commit`; current tree has uncommitted changes —
> `.env.example`, `.gitignore`, `PROJECT_HANDBOOK.md`,
> `docs/DECISIONS_LOG.md`, `docs/progress.md`,
> `frontend/src/app/pages/Chat.tsx`, `frontend/src/app/pages/Library.tsx`
> modified, the stray `frontend/...zip` deleted, plus untracked
> `docs/Financial_RAG_Project_Structure.md`, `docs/architecture.md`,
> `frontend/.env.example`, `frontend/src/app/lib/`, `migrations/`,
> `scripts/`, `services/api/alembic.ini`, `services/api/pyproject.toml`,
> `services/api/src/`, `services/api/tests/`). Verified by reading files
> and running each phase's own commands (`mypy`, `ruff`, `pytest`, a real
> `alembic upgrade head`, a real `uvicorn` boot, `curl` against every
> endpoint including real multipart uploads, `scripts/seed_dev_data.py`
> run twice to confirm idempotency, and a full headless-Playwright pass
> against the actual running frontend + backend) — not by folder
> existence.

## Build Order Status

| # | Phase | Status | Reason |
|---|-------|--------|--------|
| 1 | Fix Search crash | **Done** | [Chat.tsx:70](../frontend/src/app/pages/Chat.tsx#L70) renders `<SearchIcon .../>`, matching the aliased import at [Chat.tsx:230](../frontend/src/app/pages/Chat.tsx#L230). See `docs/DECISIONS_LOG.md` 2026-08-07 entry. |
| 2 | DB schema | **Done** | All 11 ER entities from `docs/architecture.md` §7 exist as typed SQLAlchemy 2.0 models under [services/api/src/models/db/](../services/api/src/models/db). `pytest tests\unit -v` (3/3) re-verified clean this phase alongside Phase 4's model change. See the seven `docs/DECISIONS_LOG.md` entries dated 2026-08-07. |
| 3 | FastAPI skeleton | **Done** | `main.py` registers every v1 router + three middleware stubs (now also `CORSMiddleware`, added this phase — see below). All 11 planned endpoints exist, fully typed. See the `docs/DECISIONS_LOG.md` entry dated 2026-08-08. |
| 4 | Library page vertical slice | **Done** | `GET/POST /documents` are real (not stubs): `GET` returns every `Document` joined with its `Company`; `POST` accepts a real multipart PDF upload, find-or-creates the `Company` by ticker, saves the PDF to local disk, writes a `Document` row (`status=pending`), and enqueues a real (no-op) Celery task. [Library.tsx](../frontend/src/app/pages/Library.tsx) fetches real data and its upload dialog posts real uploads — `MOCK_DOCS` is gone. Verified end-to-end with a headless-Playwright run against the actual running frontend + backend (screenshots showed real seeded rows, a submitted upload appearing live, zero console errors) — not just `curl`. See the five `docs/DECISIONS_LOG.md` entries dated 2026-08-08 (Phase 4). |
| 5 | Ingestion pipeline | **Not Started** | `services/ingestion` has only `requirements.txt`; zero application code. Phase 4's Celery stub task (`services/api/src/infra/celery_app.py`) is registered under the task name (`ingest_document`) Phase 5's real task will reuse. |
| 6 | Retrieval/generation pipeline | **Not Started** | `POST /query`/`POST /query/followup` exist as typed stubs (Phase 3) but return placeholder data; no retrieval or generation logic exists yet. |
| 7 | Remaining pages | **In Progress (UI-only)** | Chat, Compare, Admin all still hardcoded mock data. `GET /admin/analytics` and `GET /admin/flagged-answers` exist as typed stubs (Phase 3) but return placeholder data. |
| 8 | Eval/observability | **Not Started** | `eval/` directory exists, zero files. |
| 9 | Deployment | **Not Started** | No `Dockerfile`, no prod compose file, no `.github/workflows` files. |

## File Inventory

### frontend/ — Phase 4 output

| Path | Status | Description |
|------|--------|-------------|
| [src/app/pages/Library.tsx](../frontend/src/app/pages/Library.tsx) | Complete | `MOCK_DOCS` removed entirely. Fetches real `Document` rows on mount (loading/error/retry states) via `lib/api.ts`; a new hand-rolled upload dialog (matching `Layout.tsx`'s existing modal styling, not the unused shadcn `Dialog`) posts a real `multipart/form-data` upload and prepends the created row on success. Status badge now handles all four `DocumentStatus` values (`pending`/`processing` → "Processing", `completed` → "Indexed", `failed` → new "Failed" state). |
| [src/app/lib/api.ts](../frontend/src/app/lib/api.ts) | Complete (new) | Shared fetch client: `API_BASE_URL` (from `VITE_API_BASE_URL`, defaults to `http://localhost:8001/api/v1` — moved off uvicorn's own default of 8000 in a same-day setup fix, port 8000 being permanently occupied on this dev machine by an unrelated project's Docker container; see `docs/DECISIONS_LOG.md`'s 2026-08-09 entry), TS types hand-mirroring `models/schemas/document.py`'s Pydantic schemas, `fetchDocuments`/`uploadDocument`, and FastAPI-error-envelope parsing. |
| [.env.example](../frontend/.env.example) | Complete (new) | Documents `VITE_API_BASE_URL`. |

### frontend/ (Figma/shadcn export, UI mockup — everything else unchanged this phase)

Same state as the previous snapshot for every page except `Library.tsx`
(see git history for the full table).

### services/api/ — Phase 4 output (Phase 3 output unchanged, listed after)

| Path | Status | Description |
|------|--------|-------------|
| [src/models/db/enums.py](../services/api/src/models/db/enums.py) | Updated | Added `DocumentStatus` (`PENDING`/`PROCESSING`/`COMPLETED`/`FAILED`) — the Phase 2-flagged gap, resolved this phase. |
| [src/models/db/document.py](../services/api/src/models/db/document.py) | Updated | Added `title: Mapped[str]` and `status: Mapped[DocumentStatus]` (default `PENDING`) — both additive columns, both Phase 2-flagged gaps. |
| [src/infra/storage.py](../services/api/src/infra/storage.py) | Complete (new) | `save_uploaded_pdf` — writes an uploaded PDF to local disk under `<repo root>/data/uploads/<document_id><ext>` (overridable via `UPLOAD_DIR`). Local-disk only; not S3/blob storage (not in the agreed stack). |
| [src/infra/celery_app.py](../services/api/src/infra/celery_app.py) | Complete (new) | `celery_app` (Redis-backed) + a genuinely-registered no-op `ingest_document` task. Producer-side only — `services/ingestion` gets its own instance in Phase 5, agreeing only by broker URL + task name, not shared code. |
| [src/api/v1/routes/documents.py](../services/api/src/api/v1/routes/documents.py) | Complete (real logic) | `GET /documents` — every `Document` joined-loaded with `Company`, newest first, **not** filtered by `tenant.org_id` (deliberate — see decisions log: documents are shared reference data across orgs, not owned by one). `POST /documents` — real multipart upload (`UploadFile` + individual `Form(...)` fields), find-or-create `Company` by ticker, saves the PDF via `infra/storage.py`, writes a `Document` row (`status=pending`), enqueues the stub Celery task (failure to enqueue logs a warning, doesn't fail the request). |
| [src/models/schemas/document.py](../services/api/src/models/schemas/document.py) | Updated | `DocumentCreateRequest` removed (replaced by individual route-level `Form(...)` params — a Pydantic submodel next to `File(...)` doesn't flatten the way a plain HTML form posts, confirmed by testing). Added `CompanyResponse` (nested on `DocumentResponse`) and `title`/`status` fields. |
| [src/main.py](../services/api/src/main.py) | Updated | Added `CORSMiddleware` (outermost of all middleware), required for `Library.tsx`'s browser `fetch` calls — missing CORS was invisible to every non-browser check (`curl`, `mypy`, `ruff`, `pytest`) and only surfaced via an actual Playwright-driven browser run. Allowed origins default to Vite's dev ports, overridable via `CORS_ALLOWED_ORIGINS`. |
| [pyproject.toml](../services/api/pyproject.toml) | Updated | Added `[[tool.mypy.overrides]]` for `celery.*` (`ignore_missing_imports = true`) — celery ships no type stubs/`py.typed` marker. |
| [tests/unit/test_models.py](../services/api/tests/unit/test_models.py) | Updated | `_make_document_chunk`'s `Document(...)` construction now passes `title=` (newly required, not-null column) — 3/3 tests re-verified passing. |

### services/api/ — Phase 2/3 output (unchanged this phase, re-verified)

| Path | Status | Description |
|------|--------|-------------|
| [requirements.txt](../services/api/requirements.txt) | Complete (pre-work) | Unchanged; `python-multipart` (already present since Phase 2 pre-work) is what makes Phase 4's real file upload work with no new dependency. |
| [alembic.ini](../services/api/alembic.ini) | Complete | Unchanged. |
| [src/models/db/*.py](../services/api/src/models/db) (other 10 entity files + `base.py` + `__init__.py`) | Complete | Unchanged. |
| [src/infra/db.py](../services/api/src/infra/db.py) | Complete | Unchanged. |
| [src/api/v1/deps.py](../services/api/src/api/v1/deps.py), [src/api/middleware/*.py](../services/api/src/api/middleware) | Complete | Unchanged. |
| [src/api/v1/routes/{query,conversations,citations,health,admin}.py](../services/api/src/api/v1/routes) | Complete (stub) | Unchanged — still Phase 3 placeholders; `documents.py` is the only route file with real logic so far. |

### migrations/ (repo root)

| Path | Status | Description |
|------|--------|-------------|
| [env.py](../migrations/env.py), [script.py.mako](../migrations/script.py.mako) | Complete | Unchanged. |
| [versions/1366ef359569_initial_schema.py](../migrations/versions/1366ef359569_initial_schema.py) | Applied | Unchanged (Phase 2's initial schema). |
| [versions/e0bad18df9c5_initial_schema.py](../migrations/versions/e0bad18df9c5_initial_schema.py) | Applied | Pre-existing empty/no-op migration found already chained onto the initial schema at the start of this phase (not created this phase) — harmless, left in place rather than rewriting migration history. |
| [versions/8c520544e49c_add_document_title_and_status.py](../migrations/versions/8c520544e49c_add_document_title_and_status.py) | Applied (new) | Adds `documents.title`/`documents.status` + the `document_status` Postgres enum. Autogenerate's raw output was incomplete (missing an explicit `CREATE TYPE` for the new enum on an *existing* table — see decisions log) and was hand-corrected before applying. Verified: failed once cleanly (transactional DDL rolled back with zero partial state), fixed, re-ran successfully. |

### scripts/ (repo root)

| Path | Status | Description |
|------|--------|-------------|
| [seed_dev_data.py](../scripts/seed_dev_data.py) | Complete (new) | Loads 4 companies (NVDA/AMD/INTC/TSM) + 6 documents mirroring the old `MOCK_DOCS` data, idempotently (application-level check, not a DB constraint). Verified by running it twice: first run 6 created/0 skipped, second run 0 created/6 skipped. |

### Everything else (unchanged this phase)

| Area | Status |
|------|--------|
| `services/ingestion` | Only `requirements.txt` + `venv/`. Zero application code. |
| `packages/shared` | Empty. |
| `infra/k8s`, `infra/terraform` | Empty. |
| `eval` | Empty. |
| `.github/workflows` | Empty. |
| `docs` | `architecture.md` and `Financial_RAG_Project_Structure.md` unchanged this phase. |
| `data/uploads/` | New, gitignored — where `POST /documents` actually writes uploaded PDFs locally. Empty in the committed tree; contains test-upload artifacts only transiently during manual verification (cleaned up after). |

## Known Issues / Bugs

**Frontend known-issue checklist** — unchanged from the previous
snapshot; see git history for the full table (unused shadcn components,
disconnected dark-mode tokens on the shadcn `Dialog` primitive
specifically confirmed still relevant this phase — see Deviations below
— missing aria-labels, dead MUI/Emotion deps, `react`/`react-dom` as
optional peerDeps, missing `tsconfig.json` — none fixed this phase,
none newly introduced by it).

**Phase 4-specific notes:**
- `GET /documents` is **not** filtered by `tenant.org_id`, on purpose —
  see `docs/DECISIONS_LOG.md`'s "Documents are shared reference data"
  entry. If a future phase needs per-tenant visibility restrictions over
  the shared corpus, that's a join table, not an `org_id` FK on
  `Document`.
- `POST /documents`'s company find-or-create has an accepted, unguarded
  race on a brand-new ticker under concurrent requests (documented
  in-code and in the decisions log) — fine for single-analyst local
  dev/demo, not fine for a real multi-writer production path.
- No `GET /companies` endpoint exists yet — `POST /documents` creates
  companies implicitly via find-or-create; there's no way to list/browse
  companies independently of their documents yet.
- No `GET /documents/{id}/file` endpoint — the Library page's
  Download/MoreHorizontal row actions remain inert placeholders, same as
  the old mock (uploaded files are retrievable only by reading
  `data/uploads/` directly, or via `Document.source_url`).
- Local-disk file storage (`data/uploads/`) only works because
  `services/api` and `services/ingestion` share a filesystem in local dev
  — Phase 9 (deployment) needs a real shared object store instead.
- `CORS_ALLOWED_ORIGINS` defaults cover Vite's default dev port (`5173`)
  and `3000`; anyone running the frontend on a different port needs to
  set this env var or `GET /documents` will fail in the browser with a
  CORS error (not a 4xx/5xx — the request never completes from the
  frontend's point of view).

**Grep for TODO/FIXME/XXX/NotImplementedError/bare `pass`:** No matches
under `services/api/src` or `frontend/src/app/lib` (checked as part of
this phase).

## Deviations From the Original Plan

- **`GET /documents` deliberately does not implement literal
  `tenant.org_id` row-filtering**, even though `PROJECT_HANDBOOK.md`'s
  Phase 4 prompt says "scoped by tenant context." Surfaced explicitly as
  an ER-model gap (`docs/architecture.md` §7 has no relationship between
  `ORGANIZATION` and `COMPANY`/`DOCUMENT` at all) and resolved via an
  explicit choice (shared corpus, no row filtering — SEC filings are
  public data) rather than silently adding an `org_id` FK, which
  `CLAUDE.md` §4 would have required flagging first anyway. Full
  reasoning in `docs/DECISIONS_LOG.md`.
- **`POST /documents`'s request shape is real multipart file upload with
  individual `Form(...)` fields, not the Phase 3 stub's JSON body or a
  Pydantic form-model.** A Pydantic model as `Form(...)` (FastAPI's own
  documented pattern) was tried first and found, by live-testing, to nest
  incorrectly when combined with a sibling `File(...)` param — switched to
  one `Form(...)` parameter per field instead. See decisions log.
- **`CORSMiddleware` added to `main.py`**, not part of any phase's
  originally-planned file list — necessary the moment any frontend page
  makes a real cross-origin browser `fetch` call, which first happens
  this phase. Every non-browser check (`curl`, `mypy`, `ruff`, `pytest`)
  passed without it; only caught via an actual Playwright-driven browser
  run against the real dev server.
- **Local-disk PDF storage (`services/api/src/infra/storage.py`,
  `data/uploads/`)** is new, unplanned infrastructure — needed because
  Phase 4's DoD requires an actual PDF upload to work, and nothing in the
  agreed stack (`CLAUDE.md` §3) covers file storage yet. Explicitly
  flagged as a Phase-9-must-revisit (real deployment needs a shared
  object store, not a shared local filesystem).
- Everything from the previous snapshot's deviations list (Phase 3's
  health-check exception, the `ruff` bugbear config, `docs/architecture.md`
  supplied mid-Phase-2, `DocumentChunk.chunk_index` added beyond the
  pasted ER diagram, model-layer tests added a phase early, frontend
  scaffolded ahead of backend) still stands and wasn't touched this
  phase.

## Immediate Next Step

Phase 4 is done — the Library page is a real, verified vertical slice
from browser click to Postgres row and back (and back again, rendered).
Next up is **Phase 5: the ingestion pipeline** (`PROJECT_HANDBOOK.md` §6)
— `services/ingestion/src/` still has zero application code. Phase 5
needs to: implement `document_classifier.py`, `pdf_parser.py`,
`layout_segmenter.py`, `table_extractor.py`, `agentic_chunker.py`/
`table_chunker.py`, `embedder.py`, and `qdrant_writer.py`/
`metadata_writer.py`, then wire all of it into a real
`tasks/ingest_document.py` Celery task **registered under the same
`"ingest_document"` task name** Phase 4's stub already uses in
`services/api/src/infra/celery_app.py` — so anything already sitting in
the Redis queue from Phase 4 testing/demo gets picked up with no rename.
The real task should read the PDF from `Document.source_url` (a path
under `data/uploads/`, written by Phase 4's `infra/storage.py`) and, on
completion, flip `Document.status` from `PENDING` through `PROCESSING` to
`COMPLETED`/`FAILED` — the enum already has all four values Phase 5
needs, added proactively this phase. Nothing in Phase 5 is blocked; run
the Celery worker with `--pool=solo` on Windows per `PROJECT_HANDBOOK.md`
§5.
