# PROJECT_HANDBOOK.md — Aegis Intelligence: Complete Implementation Handbook

This is the durable reference for building, running, and shipping this
project. `CLAUDE.md` tells Claude Code *how* to behave; this file tells
both of you *what* to build, in what order, with what commands, and how to
verify each step before moving on.

---

## 0. How to use this handbook

Each phase in §6 has the same five parts:

1. **Goal** — one sentence, what this phase achieves.
2. **Prerequisites** — which prior phase(s) must be done first.
3. **What gets built** — the concrete file list.
4. **Claude Code prompt** — copy-paste this into a Claude Code session
   opened at the repo root. Edit it if your situation has drifted from the
   plan, but the intent should stay intact.
5. **Definition of Done** — commands *you* run yourself to verify, plus
   what should now be true in `docs/progress.md` and `docs/DECISIONS_LOG.md`.

**Your loop, each phase:** open the phase section -> paste the prompt into
Claude Code -> review the diff it produces -> read the new
`docs/DECISIONS_LOG.md` entry (this is where the actual learning happens -
don't skip it) -> run the DoD commands yourself -> only then move to the
next phase. Don't let Claude Code jump ahead to a later phase's files even
if it offers to; each phase is a checkpoint on purpose.

---

## 1. Project Positioning

**Problem:** analysts spend hours manually reading 10-Ks, 10-Qs, and
earnings call transcripts to answer questions like "how did data center
revenue trend over the last 4 quarters, and what did management say about
supply constraints?" - because the number and the narrative never live in
the same place, and dense financial tables don't survive naive text
extraction.

**Why it's a strong portfolio pick:** every advanced RAG technique you
already know is load-bearing here, not decorative - hybrid search, RRF,
agentic chunking, reranking, multi-modal (table) handling, and
history-aware retrieval all solve a real problem in this specific domain.
The differentiator on top of that is the eval story: financial numbers are
objectively checkable, so the project can produce a real number
("X% of extracted figures matched the source table exactly") instead of a
vague "answers seem good" claim. That combination - grounded numerics +
measured eval - is the single hardest unsolved RAG problem in industry
right now, and naming it explicitly in an interview signals you understand
production RAG failure modes, not just the happy path.

**Target roles:** GenAI Engineer, RAG Engineer, MLOps Engineer, 2026-2027
hiring cycle.

---

## 2. Complete Tech Stack

| Layer | Choice | Why this, not the obvious alternative |
|---|---|---|
| API framework | FastAPI | Async-native, Pydantic request/response validation, auto-generated OpenAPI docs - the last one matters for a portfolio project because it's a free "here's my API surface" artifact. |
| ORM | SQLAlchemy 2.0 (`Mapped`/`mapped_column`) + Alembic | Typed models catch schema/query mistakes at write-time; Alembic gives versioned, reviewable migrations instead of hand-run SQL. |
| Relational store | PostgreSQL | ACID metadata store - orgs, users, conversations, citations, eval results. Kept separate from the vector DB deliberately (see §3). |
| Vector store | Qdrant | Strong native metadata filtering (ticker, date, fiscal quarter, document type) alongside vector search - you need to filter *and* search semantically in the same query. |
| Async task queue | Celery + Redis | Decouples slow batch ingestion from fast real-time querying - the single most important infra decision in this project (see §3). |
| Reranking | Cohere rerank | Resolves the case where the same metric ("revenue") appears near-identically across multiple quarters' filings - pure vector similarity can't tell them apart, rerank can. |
| PDF/table parsing | pymupdf + camelot | Layout-aware: narrative text, tables, and footnotes are extracted separately. A financial table parsed as flat text loses row/column relationships - that's the direct cause of numeric hallucination this project exists to prevent. |
| Frontend | React + TypeScript + Vite + shadcn/Radix + Tailwind | Already scaffolded via Figma export; being wired to real data phase-by-phase starting Phase 4. |
| Eval | RAGAS or DeepEval | Automated retrieval-precision and groundedness scoring against a gold Q&A set - turns "I think it's accurate" into a number you can regression-test in CI. |
| Tracing/observability | LangSmith or Arize Phoenix | Full trace of every retrieval + generation step - needed to debug *why* a specific answer went wrong, not just *that* it did. |
| CI/CD | Docker + GitHub Actions | Build/test on every PR, nightly eval-regression gate, staged deploy. The eval gate specifically is the MLOps differentiator most portfolio RAG projects skip entirely. |

---

## 3. How Everything Connects

Two pipelines, deliberately decoupled, joined by one identifier.

**Ingestion pipeline (offline, batch):** upload -> classify document type
-> layout-aware parse (narrative / tables / footnotes split apart) -> table
extraction (structured, never flattened) -> agentic chunking of narrative
sections -> embed both chunk types -> write vectors + light metadata to
Qdrant, write full relational metadata to Postgres.

**Query pipeline (real-time):** question in -> follow-up? apply
history-aware reformulation -> multi-query expansion -> hybrid retrieval
(BM25 + dense, in parallel) -> RRF fusion -> Cohere rerank -> confidence
check -> context assembly -> grounded generation -> numeric verification
against source -> response with citations.

**The join:** every chunk written during ingestion carries a
`source_location` (document ID, page number, and either a table-cell
reference or a text span). That identifier is created once, at ingestion
time, and travels unchanged through retrieval into the final citation
object - it is never regenerated or re-derived. That's what guarantees a
citation always points to something real instead of a plausible-looking
fabrication.

**Why the pipelines are separate services, not one app:** a spike in
analyst queries shouldn't be bottlenecked by a batch of new filings being
ingested, and vice versa. They scale independently in production (see §7).

Full mermaid diagrams, the decision/failure-path tables, and the ER model
live in `docs/architecture.md` - read that alongside this section, it has
the diagrams this file doesn't repeat.

---

## 4. Repo Structure Map

```
financial-rag-platform/  (repo root - CLAUDE.md and this file live here)
├── services/
│   ├── api/            # real-time query service (FastAPI)
│   │   └── src/{api,core,models,infra,observability}/
│   └── ingestion/       # async/batch document processing (Celery)
│       └── src/{tasks,parsing,chunking,embedding,storage,infra}/
├── packages/shared/      # code shared between api and ingestion
├── migrations/           # Alembic migrations for Postgres
├── infra/{terraform,k8s}/
├── eval/                 # RAGAS/DeepEval harness, gold Q&A set
├── scripts/               # dev-data seeding, one-off utilities
├── docs/
│   ├── architecture.md
│   ├── progress.md
│   └── DECISIONS_LOG.md
├── frontend/             # React/TS app (Figma export)
├── .github/workflows/
├── docker-compose.yml
└── docker-compose.prod.yml
```

Full annotated tree with every planned file is in
`Financial_RAG_Project_Structure.md` in the project's reference docs - this
is the condensed map for day-to-day orientation.

---

## 5. One-Time Environment Setup (Windows / PowerShell)

Run once, in order. Skip anything already installed.

**5.1 Core tools**
```powershell
winget install Python.Python.3.12
winget install OpenJS.NodeJS.LTS
winget install Docker.DockerDesktop
winget install Git.Git
```
Restart the terminal after installing so `PATH` updates take effect.

**5.2 Claude Code**
```powershell
irm https://claude.ai/install.ps1 | iex
```
Then `claude --version` to confirm, and `claude` from the repo root to log
in and start a session. If you use the VS Code extension instead of the
terminal, install it from the VS Code marketplace - it reads the same
`CLAUDE.md` automatically. Git for Windows is optional but recommended:
without it Claude Code uses the PowerShell tool for shell commands, with it
it can use Git Bash - either works fine for this project.

**5.3 Python environments - one venv per service**
```powershell
cd services\api
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
cd ..\ingestion
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
cd ..\..
```
If `Activate.ps1` is blocked by execution policy, run once (per machine, as
your user, not admin):
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

**5.4 Frontend**
```powershell
cd frontend
npm install
cd ..
```

**5.5 Local infra**
```powershell
Copy-Item .env.example .env    # then fill in real values
docker compose up -d
docker compose ps               # confirm postgres, qdrant, redis are healthy
```

**5.6 Git**
```powershell
git init
git add .
git commit -m "Initial commit"
```
Doing this now (if not already done) means every future `docs/progress.md`
snapshot can use real commit history instead of guessing from file state.

**Windows-specific gotcha worth knowing now:** Celery's default `prefork`
worker pool doesn't work on native Windows. Local dev runs the worker with
`--pool=solo` (single-threaded, fine for local testing of one document at a
time). This only matters starting Phase 5 - noted here so it doesn't
surprise you later.

---

## 6. The Nine-Phase Plan

### Phase 1 - Fix the Chat.tsx crash

**Goal:** stop the frontend from throwing on the empty-project Chat view.

**Prerequisites:** none.

**What gets built:** one-line fix in `frontend/src/app/pages/Chat.tsx`.

**Claude Code prompt:**
> In `frontend/src/app/pages/Chat.tsx`, a component renders `<Search .../>`
> but only `SearchIcon` is imported (aliased from lucide-react). Find every
> use of the undefined `Search` reference and fix it to use the correctly
> imported icon, without changing any other logic in the file. Then append
> an entry to `docs/DECISIONS_LOG.md` per the template in `CLAUDE.md` §5,
> and update the Phase 1 row in `docs/progress.md` to Done.

**Definition of Done:**
```powershell
cd frontend
npm run dev
```
Navigate to the empty-project Chat view - no runtime error. Then:
```powershell
Select-String -Path src\app\pages\Chat.tsx -Pattern "\bSearch\b"
```
confirms every reference resolves to the actual imported name.

---

### Phase 2 - DB schema (SQLAlchemy 2.0 models)

**Goal:** all 11 ER entities exist as typed SQLAlchemy 2.0 models with a
working Alembic migration.

**Prerequisites:** Phase 1 (independent, but keep the build order clean).

**What gets built:** `services/api/src/models/db/{base,enums,organization,
user,company,document,document_chunk,table_data,conversation,query,answer,
citation,eval_result}.py`, plus the first Alembic migration, plus
`services/api/tests/unit/{conftest.py,test_models.py}` — model-layer tests
now start in Phase 2 rather than first appearing in Phase 6 (see
`docs/DECISIONS_LOG.md`'s entry for `tests/unit/conftest.py` +
`test_models.py` for why).

**Claude Code prompt:**
> Implement the SQLAlchemy 2.0 models under `services/api/src/models/db/`
> for all 11 entities in the ER model in `docs/architecture.md` §7, in this
> exact order: `base.py` (DeclarativeBase + a shared naming convention for
> constraint names, which Alembic autogenerate needs to produce stable
> diffs), `enums.py` (Python enums for document_type, chunk_type, user
> role, org tier), then `organization.py -> user.py -> company.py ->
> document.py -> document_chunk.py -> table_data.py -> conversation.py ->
> query.py -> answer.py -> citation.py -> eval_result.py`. Every model uses
> `Mapped[...]`/`mapped_column(...)`, full PEP 484 typing, and the
> relationships implied by the ER diagram's cardinality (e.g. Document
> `1--*` DocumentChunk). After all 11 models exist, generate the first
> Alembic migration and apply it against the local Postgres from
> `docker-compose.yml`. Then, for each entity (or logical group of related
> entities), append a `docs/DECISIONS_LOG.md` entry per `CLAUDE.md` §5 -
> don't wait until all 11 are done to write the log, write as you go so the
> reasoning stays specific to what was just built. Update
> `docs/progress.md` when finished.

**Definition of Done:**
```powershell
cd services\api
.\venv\Scripts\Activate.ps1
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
mypy src\models\db
pytest tests\unit -v
```
`alembic upgrade head` succeeds against the Dockerized Postgres; `mypy`
reports no errors; all 11 tables are visible via `docker exec` + `psql
\dt`. `docs/DECISIONS_LOG.md` has at least one entry per entity or entity
group.

---

### Phase 3 - FastAPI skeleton with stub endpoints

**Goal:** a running API with every planned route registered and typed, all
returning placeholder data - proves the surface area before the logic
exists.

**Prerequisites:** Phase 2.

**What gets built:** `main.py`, `api/v1/routes/{query,documents,
conversations,citations,health,admin}.py`, `api/v1/deps.py`, `api/
middleware/{auth,tenant_context,rate_limit}.py`, Pydantic schemas under
`models/schemas/`.

**Claude Code prompt:**
> Build the FastAPI skeleton in `services/api/src/`: `main.py` as the app
> entrypoint registering all v1 routers; stub routes for `query.py`
> (`POST /query`, `POST /query/followup`), `documents.py`
> (`GET/POST /documents`), `conversations.py`, `citations.py`, `health.py`
> (liveness/readiness), and `admin.py`. Each stub returns a typed Pydantic
> response model with placeholder/empty data, not real logic yet - the
> point of this phase is a correct, fully-typed API surface, not working
> retrieval. Add `deps.py` with dependency-injected DB session and a
> tenant-context stub, and middleware stubs for auth, tenant resolution,
> and rate limiting. Full PEP 484 typing throughout. Append the
> `docs/DECISIONS_LOG.md` entry and update `docs/progress.md`.

**Definition of Done:**
```powershell
cd services\api
.\venv\Scripts\Activate.ps1
uvicorn src.main:app --reload
```
`http://localhost:8000/health` returns 200; `http://localhost:8000/docs`
lists every planned endpoint with correct request/response schemas.

---

### Phase 4 - Wire the Library page end-to-end (thin vertical slice)

**Goal:** one real path from browser click to Postgres row and back -
proves the whole stack connects before building out the RAG core.

**Prerequisites:** Phases 2-3.

**What gets built:** real `GET /documents` and `POST /documents` logic,
`scripts/seed_dev_data.py`, `frontend/src/app/pages/Library.tsx` updated to
fetch real data and POST real uploads instead of using `MOCK_DOCS`.

**Claude Code prompt:**
> Wire the Library page to real data. In `services/api`, implement
> `GET /documents` to query Postgres for real `Document` rows (scoped by
> tenant context) and `POST /documents` to create a `Document` row with
> status `pending` and enqueue a stub Celery task (the task can be a
> no-op placeholder - real ingestion is Phase 5). Write
> `scripts/seed_dev_data.py` to load a handful of fake `Document` rows for
> local testing. In `frontend/src/app/pages/Library.tsx`, replace
> `MOCK_DOCS` with a real fetch to the API and wire the upload UI to
> `POST /documents`. Append the `docs/DECISIONS_LOG.md` entry and update
> `docs/progress.md`.

**Definition of Done:** upload a PDF through the running frontend; confirm
a real row appears in Postgres:
```powershell
docker exec -it <postgres-container> psql -U postgres -d aegis -c "SELECT * FROM documents;"
```
Library page renders that real row, not mock data.

---

### Phase 5 - Ingestion pipeline (the RAG core, write path)

**Goal:** a real PDF goes in, structured chunks + tables come out, with a
consistent `source_location` in both Qdrant and Postgres.

**Prerequisites:** Phase 4 (needs the real `Document` row + Celery task
hook already wired).

**What gets built:** `services/ingestion/src/{tasks/ingest_document.py,
parsing/*, chunking/*, embedding/*, storage/*}`.

**Claude Code prompt:**
> Implement the ingestion pipeline in `services/ingestion/src/`:
> `document_classifier.py` (filing vs. transcript vs. deck),
> `pdf_parser.py` (pymupdf), `layout_segmenter.py` (splits narrative /
> table / footnote regions), `table_extractor.py` (camelot, structured
> output - never flatten a table to text), `agentic_chunker.py`
> (LLM-assisted narrative section boundaries) and `table_chunker.py`
> (never splits a table mid-row), `embedder.py`, and
> `qdrant_writer.py`/`metadata_writer.py` writing to Qdrant and Postgres
> respectively with a shared `source_location` (document ID, page number,
> table-cell or text-span reference) built once and passed through
> unchanged. Wire all of it into `tasks/ingest_document.py` as the real
> Celery task replacing Phase 4's no-op. On Windows, run the worker with
> `--pool=solo` locally. Append the `docs/DECISIONS_LOG.md` entry per
> pipeline stage (not one giant entry) and update `docs/progress.md`.

**Definition of Done:**
```powershell
cd services\ingestion
.\venv\Scripts\Activate.ps1
celery -A src.infra.celery_app worker --pool=solo --loglevel=info
```
Upload one real 10-K through the frontend; confirm in Postgres that
`DocumentChunk` and `TableData` rows exist with sane counts, and in Qdrant
that the same number of vectors exist with matching `source_location`
metadata.

---

### Phase 6 - Retrieval/generation wired to Chat (the RAG core, read path)

**Goal:** ask a real question, get a grounded answer with real citations.

**Prerequisites:** Phase 5 (needs real ingested data to retrieve against).

**What gets built:** `services/api/src/core/{retrieval/*,generation/*,
conversation/*,citation/*}`, real `POST /query` and `/query/followup`
logic, `frontend/src/app/pages/Chat.tsx` wired to the real API.

**Claude Code prompt:**
> Implement the query pipeline in `services/api/src/core/`:
> `bm25_retriever.py`, `dense_retriever.py`, `hybrid_retriever.py` (runs
> both in parallel), `rrf.py`, `reranker.py` (Cohere), `multi_query.py`;
> `history_manager.py` for follow-up reformulation; `answer_generator.py`
> (LLM call strictly grounded in retrieved context - no claims beyond what
> is retrieved), `numeric_verifier.py` (checks every numeric claim against
> the source chunk/table it cites), `confidence_scorer.py`; and
> `citation_resolver.py` mapping a retrieved chunk back to its
> `source_location`. Wire all of it into real `POST /query` and
> `POST /query/followup` logic in `api/v1/routes/query.py`, replacing the
> Phase 3 stubs. Update `frontend/src/app/pages/Chat.tsx` to call the real
> API instead of mock Q&A. Append `docs/DECISIONS_LOG.md` entries per
> pipeline stage and update `docs/progress.md`.

**Definition of Done:** ask a real question in the Chat UI against the 10-K
ingested in Phase 5; get back an answer with citations pointing to a real
page number; ask a numeric question and confirm the number matches the
source table exactly.

---

### Phase 7 - Remaining pages (Compare, Admin)

**Goal:** no mock arrays remain anywhere in the frontend.

**Prerequisites:** Phase 6.

**What gets built:** real endpoints + wiring for `Compare.tsx` (metric
comparison across quarters) and `Admin.tsx` (analytics dashboard, flagged
answers review).

**Claude Code prompt:**
> Wire `frontend/src/app/pages/Compare.tsx` and `Admin.tsx` to real data.
> For Compare, implement an endpoint that pulls the same metric across
> multiple ingested quarters/documents for a company and returns a
> comparison payload. For Admin, implement endpoints backing the KPI
> cards, the revenue-over-time chart, and the flagged-answers review table
> (reading from the `Answer`/`Citation` tables and any flag field). Remove
> the remaining `MOCK_METRICS` and inline mock arrays. Append the
> `docs/DECISIONS_LOG.md` entry and update `docs/progress.md`.

**Definition of Done:** grep confirms zero remaining `MOCK_` references
under `frontend/src/app`; Compare and Admin pages render real query
results.

---

### Phase 8 - Eval + observability

**Goal:** a quantified, CI-gated answer to "how good is retrieval and how
grounded are the answers?"

**Prerequisites:** Phase 6 (needs a working query pipeline to evaluate).

**What gets built:** `services/api/tests/eval/eval_dataset.jsonl`,
`eval/ragas_runner.py`, `eval/retrieval_ab_test.py`, tracing hooks in
`observability/tracing.py` and `metrics.py`,
`.github/workflows/eval-regression.yml`.

**Claude Code prompt:**
> Build the eval harness. Create `services/api/tests/eval/
> eval_dataset.jsonl` with a gold set of analyst Q&A pairs (question,
> expected answer, expected source document/page) covering both narrative
> and numeric questions. Implement `eval/ragas_runner.py` running RAGAS or
> DeepEval retrieval-precision and groundedness scoring against that set
> and the real query pipeline from Phase 6. Add LangSmith or Arize Phoenix
> tracing hooks in `observability/tracing.py`, and latency/hit-rate/
> groundedness metrics in `metrics.py`. Add
> `.github/workflows/eval-regression.yml` running the eval suite on a
> schedule and failing the job if scores drop below a defined threshold.
> Append the `docs/DECISIONS_LOG.md` entry and update `docs/progress.md`.

**Definition of Done:**
```powershell
python eval\ragas_runner.py
```
produces a retrieval-precision and groundedness score; deliberately
degrading a retrieval parameter (e.g. disabling rerank) and re-running
shows the score drop and, in CI, fails the workflow.

---

### Phase 9 - Deployment

**Goal:** the full stack runs the same way in a prod-like environment as it
does locally, with CI/CD in place.

**Prerequisites:** all prior phases.

**What gets built:** `services/api/Dockerfile`,
`services/ingestion/Dockerfile`, `docker-compose.prod.yml`,
`infra/terraform/*`, `.github/workflows/{ci.yml,cd-staging.yml}`.

**Claude Code prompt:**
> Write multi-stage Dockerfiles for `services/api` and
> `services/ingestion` (build stage installs deps, slim runtime stage).
> Write `docker-compose.prod.yml` with production overrides (managed
> Qdrant Cloud / RDS endpoints instead of local containers, no bind mounts,
> restart policies). Scaffold `infra/terraform/{main.tf,variables.tf}` for
> the managed Qdrant/RDS/compute resources described in
> `docs/architecture.md` §4. Write `.github/workflows/ci.yml` (lint,
> type-check, unit + integration tests on every PR) and
> `.github/workflows/cd-staging.yml` (build + push images, deploy to
> staging on merge to main). Append the `docs/DECISIONS_LOG.md` entry and
> update `docs/progress.md`.

**Definition of Done:**
```powershell
docker compose -f docker-compose.prod.yml up
```
runs the full stack as a prod-like smoke test locally; a test PR shows a
green `ci.yml` run.

---

## 7. Deployment Handbook (beyond Phase 9's DoD)

- **Staging vs. prod env vars:** never commit real secrets - `.env.example`
  documents required keys, actual values live in GitHub Actions secrets
  (CI/CD) and your deploy target's secret manager (prod).
- **Managed services checklist:** Qdrant Cloud (free tier is enough for
  portfolio scale), a managed Postgres (RDS or Cloud SQL), managed Redis.
  Point `docker-compose.prod.yml` and Terraform vars at these instead of
  local containers.
- **Independent scaling:** API and ingestion worker scale on separate
  triggers (request volume vs. queue depth) - this is a deliberate
  interview talking point, not an afterthought; see §3.
- **Rollback:** keep the previous image tag deployable; `cd-staging.yml`
  should tag images with the commit SHA, not just `latest`, so a rollback
  is a redeploy of a known-good SHA.
- **Caching:** cache frequent/expensive queries with a short TTL - filings
  update quarterly, not in real time, so aggressive caching is safe and
  cheap.

---

## 8. Portfolio Packaging Guidance

- **Resume bullets should carry the numbers from Phase 8**, not adjectives:
  "Built a multi-modal RAG platform over SEC filings with hybrid
  retrieval and Cohere reranking; achieved X% retrieval precision and Y%
  groundedness on a gold Q&A set, gated in CI" beats "Built a RAG chatbot
  for financial documents."
- **Interview prep from `docs/DECISIONS_LOG.md`:** before an interview,
  re-read 3-4 entries covering the pieces most likely to come up (schema
  design, the hybrid retrieval + RRF + rerank chain, numeric verification,
  the eval gate) until you can explain the tradeoffs from memory, not from
  the doc.
- **Core talking points, in order of how differentiating they are:**
  1. Numeric grounding via source verification - the hardest unsolved RAG
     problem, and this project solves it explicitly.
  2. The eval-gated CI pipeline - most portfolio RAG projects skip this
     entirely.
  3. Multi-modal handling of tables as structured data, not flattened text.
  4. The decoupled ingestion/query architecture and why it scales
     independently.
- **README structure for the public repo:** problem statement -> an
  architecture diagram (reuse `docs/architecture.md`'s mermaid) -> a short
  demo GIF -> the eval numbers, front and center -> tech stack table ->
  "run it locally" instructions (this handbook's §5, condensed).

---

## 9. Command Cheat Sheet (PowerShell)

```powershell
# Activate a service venv
.\venv\Scripts\Activate.ps1

# Install deps
pip install -r requirements.txt

# DB migrations
alembic revision --autogenerate -m "message"
alembic upgrade head

# Run the API
uvicorn src.main:app --reload

# Run the ingestion worker (Windows)
celery -A src.infra.celery_app worker --pool=solo --loglevel=info

# Frontend
npm run dev
npm run build

# Local infra
docker compose up -d
docker compose down
docker compose ps

# Tests / quality gates
pytest tests\ -v
mypy src
ruff check .

# Eval
python eval\ragas_runner.py
```

---

## 10. Writing Good Claude Code Prompts (for Sam)

- Reference the phase explicitly ("Phase 5 from PROJECT_HANDBOOK.md") so
  Claude Code pulls the right context instead of guessing scope.
- If you want one file at a time instead of the whole phase in one pass,
  say so up front - otherwise Claude Code will implement the phase's full
  file list before stopping.
- After Claude Code finishes, always read the new `docs/DECISIONS_LOG.md`
  entry before running the DoD commands - if the reasoning doesn't make
  sense to you, that's the moment to ask follow-up questions, not later.
- If Claude Code proposes crossing one of the boundaries in `CLAUDE.md` §4,
  it should stop and ask - if it doesn't, that's a bug in the setup worth
  flagging back to this handbook.
