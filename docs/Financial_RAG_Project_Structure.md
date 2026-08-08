# Financial Research Intelligence Platform — Project Structure

A monorepo with two cleanly separated services (`api` for real-time queries, `ingestion` for async/batch document processing), shared code in `packages/`, and infra/eval/docs at the root. This structure is designed to be defensible in an interview — every separation maps to an actual architectural decision, not just folder tidiness.

```
financial-rag-platform/
├── .github/
│   └── workflows/
│       ├── ci.yml                        # Lint + type-check + unit/integration tests on every PR
│       ├── cd-staging.yml                 # Build+push Docker images, deploy to staging on merge to main
│       └── eval-regression.yml            # Nightly RAGAS/DeepEval run — fails build if retrieval/answer quality drops
├── .env.example                           # Template for required env vars (no real secrets committed)
├── .gitignore
├── docker-compose.yml                     # Local dev: api + ingestion worker + redis + qdrant + postgres
├── docker-compose.prod.yml                # Production overrides (no dev volumes/hot-reload)
├── Makefile                               # make dev / make test / make lint shortcuts
├── pyproject.toml                         # Root-level shared tooling config (ruff, mypy, pytest)
└── README.md

services/
├── api/                                   # Real-time query service (low-latency, user-facing)
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── src/
│   │   ├── main.py                        # FastAPI app entrypoint, router registration
│   │   │
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── routes/
│   │   │   │   │   ├── query.py           # POST /query, /query/followup
│   │   │   │   │   ├── documents.py       # upload/list endpoints (delegates heavy work to ingestion)
│   │   │   │   │   ├── conversations.py   # conversation history CRUD
│   │   │   │   │   ├── citations.py       # citation expansion/lookup
│   │   │   │   │   ├── health.py          # liveness/readiness probes
│   │   │   │   │   └── admin.py           # org-level analytics/settings
│   │   │   │   └── deps.py                # FastAPI dependency injection: auth, db session, tenant
│   │   │   └── middleware/
│   │   │       ├── auth.py                # JWT/API-key verification
│   │   │       ├── tenant_context.py      # resolves org/tenant from request, scopes all queries
│   │   │       └── rate_limit.py          # per-tenant rate limiting
│   │   │
│   │   ├── core/                          # Framework-agnostic RAG logic — the heart of the project
│   │   │   ├── retrieval/
│   │   │   │   ├── base.py                # Retriever interface — this is what makes strategies swappable
│   │   │   │   ├── bm25_retriever.py
│   │   │   │   ├── dense_retriever.py
│   │   │   │   ├── hybrid_retriever.py     # runs BM25 + dense in parallel
│   │   │   │   ├── rrf.py                 # Reciprocal Rank Fusion
│   │   │   │   ├── reranker.py            # Cohere rerank wrapper
│   │   │   │   └── multi_query.py         # query expansion into sub-queries
│   │   │   ├── generation/
│   │   │   │   ├── answer_generator.py    # LLM call, strictly grounded in retrieved context
│   │   │   │   ├── numeric_verifier.py    # checks any number in the answer against the source
│   │   │   │   ├── confidence_scorer.py   # flags low-confidence answers
│   │   │   │   └── prompts.py
│   │   │   ├── conversation/
│   │   │   │   ├── history_manager.py     # history-aware query reformulation
│   │   │   │   └── session_store.py
│   │   │   └── citation/
│   │   │       └── citation_resolver.py   # maps a retrieved chunk back to doc_id/page/table-cell/span
│   │   │
│   │   ├── models/
│   │   │   ├── schemas/                   # Pydantic request/response models
│   │   │   │   ├── query.py
│   │   │   │   ├── document.py
│   │   │   │   └── citation.py
│   │   │   └── db/                        # SQLAlchemy ORM models (metadata store, not vectors)
│   │   │       ├── organization.py
│   │   │       ├── user.py
│   │   │       ├── document.py
│   │   │       ├── conversation.py
│   │   │       ├── query.py
│   │   │       ├── answer.py
│   │   │       ├── citation.py
│   │   │       └── eval_result.py
│   │   │
│   │   ├── infra/                         # Config/connections only — zero business logic
│   │   │   ├── config.py                  # pydantic-settings, env-based (dev/staging/prod)
│   │   │   ├── qdrant_client.py
│   │   │   ├── db_session.py
│   │   │   ├── redis_client.py
│   │   │   ├── celery_app.py              # shared Celery config (also used by ingestion)
│   │   │   └── logging_config.py
│   │   │
│   │   └── observability/
│   │       ├── tracing.py                 # LangSmith / Arize Phoenix tracing hooks
│   │       └── metrics.py                 # latency, retrieval hit-rate, groundedness metrics
│   │
│   └── tests/
│       ├── unit/
│       │   ├── test_rrf.py
│       │   ├── test_reranker.py
│       │   └── test_numeric_verifier.py
│       ├── integration/
│       │   ├── test_query_endpoint.py
│       │   └── test_citation_resolution.py
│       └── eval/
│           ├── eval_dataset.jsonl         # gold Q&A pairs with known-correct answers
│           └── test_retrieval_quality.py  # RAGAS/DeepEval suite, run in CI
│
└── ingestion/                             # Async/batch document processing service
    ├── Dockerfile
    ├── requirements.txt
    ├── src/
    │   ├── worker.py                      # Celery worker entrypoint
    │   ├── tasks/
    │   │   ├── ingest_document.py         # top-level Celery task, orchestrates the steps below
    │   │   ├── reembed_documents.py       # re-run on chunking/embedding strategy change
    │   │   └── scheduled_reingest.py      # cron-triggered pickup of new filings
    │   ├── parsing/
    │   │   ├── document_classifier.py     # 10-K vs 10-Q vs transcript vs deck
    │   │   ├── pdf_parser.py              # PyMuPDF/pdfplumber wrapper
    │   │   ├── table_extractor.py         # camelot-based, outputs structured (not flattened) tables
    │   │   └── layout_segmenter.py        # splits page into narrative / table / footnote regions
    │   ├── chunking/
    │   │   ├── agentic_chunker.py         # LLM-assisted narrative section chunking
    │   │   ├── table_chunker.py           # table-aware — never splits a table mid-row
    │   │   └── base_chunker.py
    │   ├── embedding/
    │   │   ├── embedder.py                # HF/OpenAI/Cohere embedding wrapper
    │   │   └── batch_embedder.py
    │   ├── storage/
    │   │   ├── qdrant_writer.py
    │   │   └── metadata_writer.py         # writes document/chunk metadata to Postgres
    │   └── infra/
    │       ├── config.py
    │       ├── celery_app.py
    │       └── logging_config.py
    └── tests/
        ├── unit/
        │   ├── test_table_extractor.py
        │   └── test_agentic_chunker.py
        └── integration/
            └── test_full_ingestion_pipeline.py

packages/
└── shared/                                # Code shared between api and ingestion — avoids duplication/drift
    ├── pyproject.toml
    └── src/
        ├── schemas/                        # shared Pydantic models (Document, Chunk, Citation)
        ├── constants.py
        └── utils/
            ├── tenant.py                   # tenant-resolution helpers used by both services
            └── source_location.py          # canonical source-location format (doc_id, page, span)

migrations/                                 # Alembic migrations for the Postgres metadata store
├── env.py
└── versions/

infra/                                      # Deployment/infra-as-code
├── terraform/                              # AWS/GCP resources: Qdrant, RDS, ECS/Cloud Run, networking
│   ├── main.tf
│   ├── variables.tf
│   └── modules/
└── k8s/                                    # Optional — only if/when you outgrow ECS/Cloud Run
    ├── api-deployment.yaml
    └── ingestion-deployment.yaml

eval/                                        # Cross-service evaluation harness (the MLOps layer)
├── ragas_runner.py                          # runs RAGAS suite against a staging deployment
├── retrieval_ab_test.py                     # compares retrieval strategy variants quantitatively
└── reports/                                 # generated eval reports

scripts/
├── seed_dev_data.py                         # loads sample 10-Ks for local dev
└── reset_qdrant_collection.py

docs/
├── architecture.md                          # system diagram + the "why" behind each design decision
├── api_reference.md
└── runbook.md                               # on-call/ops notes — a strong production-grade signal
```

---

### Where Docker and CI actually live

- **`services/api/Dockerfile`** and **`services/ingestion/Dockerfile`** — each service builds its own image. Keep them multi-stage (build stage installs deps, runtime stage is slim) since interviewers do sometimes ask about image size.
- **`docker-compose.yml`** (root) — spins up `api`, `ingestion` (Celery worker), `redis`, `qdrant`, and `postgres` together for local dev. This is the file you'll actually run day-to-day with `docker compose up`.
- **`docker-compose.prod.yml`** (root) — production-specific overrides (env vars pointing at managed Qdrant Cloud/RDS instead of local containers, no bind-mounted source code, restart policies).
- **`.github/workflows/ci.yml`** — runs on every PR: lint (ruff), type-check (mypy), unit + integration tests for both services. This is your baseline "I have CI" proof point.
- **`.github/workflows/eval-regression.yml`** — separate, scheduled (e.g., nightly) workflow that runs the RAGAS/DeepEval suite from `eval/` against a staging deployment and fails/flags if retrieval precision or groundedness drops below a threshold. This is the file that turns "I wrote some tests" into "I built a quality-regression system" — genuinely the most interview-impressive piece of this whole structure.
- **`.github/workflows/cd-staging.yml`** — on merge to `main`: builds both Docker images, pushes to a registry (ECR/GCR), deploys to staging (ECS/Cloud Run).

### A couple of judgment calls worth knowing about

- **Monorepo vs. separate repos**: I went monorepo because at this stage (single contributor, portfolio project) it's much easier to keep `packages/shared` in sync and to demo end-to-end in one `git clone`. If this ever became a real multi-team product, splitting `api` and `ingestion` into separate repos with `shared` as a published package would be the next logical step — worth mentioning if asked in an interview, since it shows you understand the tradeoff rather than having stumbled into monorepo by default.
- **Postgres alongside Qdrant**: Qdrant holds vectors + light metadata for filtering, but Postgres holds the relational metadata store (users, orgs, conversations, citations, eval results) — this is what the `migrations/` folder is for. Some people try to cram everything into the vector DB's metadata; keeping a real relational store is part of what makes this "production-grade" rather than "vector DB tutorial."
