# Progress Snapshot — 2026-08-18 (Phase 9)

> Repo state check: real git repository, `main` branch, working tree
> clean at the start of this phase (Phase 8's own snapshot recorded its
> changes as uncommitted at handoff; those are assumed committed by Sam
> between phases per this repo's normal workflow — this phase did not
> re-verify Phase 8's git state beyond confirming its files are present
> and unchanged). This phase's own changes are uncommitted at the time of
> this snapshot. Verified by reading every new/changed file, and by real
> local execution, not by folder existence:
> - **Both Dockerfiles were actually built** this phase (Docker Desktop
>   was already running) — `docker build -f services/api/Dockerfile .`
>   and `docker build -f services/ingestion/Dockerfile .`, both from the
>   repo root, both exit code 0. Resulting images: `aegis-api:verify`
>   (555MB) and `aegis-ingestion:verify` (594MB, includes Ghostscript +
>   OpenCV's runtime libs for camelot).
> - **Both images were smoke-run**, not just built: `python -c "import
>   src.main"` / `import src.infra.celery_app` both succeeded inside their
>   respective containers; `which gs` inside `aegis-ingestion:verify`
>   confirmed Ghostscript is actually present and on `PATH`, not just
>   apt-installed and silently missing.
> - **The api image was run as a real container** (`docker run`, mapped
>   to a host port) against this repo's own already-running local
>   Postgres/Qdrant/Redis containers (from `docker-compose.yml`) via
>   `host.docker.internal`: `uvicorn` started cleanly (`Application
>   startup complete` in the logs), `GET /health` returned a real `200
>   {"status":"ok"}`, and `GET /health/ready` correctly returned a real
>   `503 {"status":"degraded","database_reachable":false}` when given
>   placeholder (not Sam's real) Postgres credentials — confirmed via a
>   direct `psycopg2.connect(...)` call inside the container that this was
>   a genuine `password authentication failed` from the real Postgres
>   server (network path proven to work end-to-end, `host.docker.internal`
>   resolved and reached the real container), not a networking failure or
>   a bug in the readiness probe. This is the expected, correct behavior
>   of an unauthenticated smoke test — this session was never given Sam's
>   real `.env` values, by design (see `.env.prod.example`'s own
>   convention) — not a defect found and left unfixed.
> - **`docker-compose.prod.yml` was syntax-validated** via `docker compose
>   -f docker-compose.prod.yml config` (using a real, filled-in
>   `.env.prod` copied from `.env.prod.example`, deleted immediately
>   after) — resolved cleanly into two services with the expected image
>   builds, env vars, and healthchecks; not run as `up` against real
>   managed endpoints (none provisioned — see Known Issues).
> - **Both new GitHub Actions workflow files were YAML-syntax-validated**
>   (`yaml.safe_load`) — neither has been run in real GitHub Actions (same
>   honest-limitation pattern as Phase 8's `eval-regression.yml` — no
>   `git push`, no repository secrets/variables configured from this
>   session).
> - **`infra/terraform/{main.tf,variables.tf}` were validated with the
>   real `terraform` CLI**, via the official `hashicorp/terraform` Docker
>   image (not installed locally, so run as `docker run
>   hashicorp/terraform ...` mounted against `infra/terraform/`): a real
>   `terraform init -backend=false` (downloaded and locked the
>   `hashicorp/aws ~> 5.0` provider, producing the committed
>   `.terraform.lock.hcl`), a real `terraform validate` (passed clean —
>   this actually checks resource attribute names/types and block nesting
>   against the real `aws` provider schema, not just brace-matching), and
>   a real `terraform fmt` (found and fixed three genuine alignment
>   inconsistencies in `main.tf`, then re-verified clean with `fmt
>   -check`). `terraform plan`/`apply` were NOT run — both need real AWS
>   credentials, which this session was never given (consistent with
>   `.env.example`'s "real secrets never typed into a session"
>   convention) and is Sam's own step. This is real, meaningfully stronger
>   verification than a hand-review, but is still short of "known to
>   actually provision" — see Known Issues for exactly what remains
>   unverified.
> - Both build/run smoke-test containers were removed after inspection
>   (`docker rm -f`); no aegis-* images or containers were left running.
>   The three pre-existing local infra containers
>   (`financialresearchintelligenceplatform-{postgres,qdrant,redis}-1`)
>   were left exactly as they were found (already running from a prior
>   session), matching every prior phase's precedent of not touching infra
>   this phase's own work doesn't need to change.

## Build Order Status

| # | Phase | Status | Reason |
|---|-------|--------|--------|
| 1 | Fix Search crash | **Done** | Unchanged this phase. |
| 2 | DB schema | **Done** | Unchanged this phase. |
| 3 | FastAPI skeleton | **Done** | Unchanged this phase. |
| 4 | Library page vertical slice | **Done** | Unchanged this phase. |
| 5 | Ingestion pipeline | **Done** | Unchanged this phase. |
| 6 | Retrieval/generation pipeline | **Done** | Unchanged this phase. |
| 7 | Remaining pages (Compare, Admin) | **Done** | Unchanged this phase. |
| 8 | Eval/observability | **Done** | Unchanged this phase. |
| 9 | Deployment | **Done** | Multi-stage Dockerfiles for both services (built + smoke-run this phase, see header), `docker-compose.prod.yml` + `.env.prod.example` (syntax-validated), `infra/terraform/{main.tf,variables.tf}` (hand-reviewed scaffold, not `plan`/`apply`-verified — see Known Issues), `.github/workflows/{ci.yml,cd-staging.yml}` (YAML-valid, never run in real GitHub Actions — see Known Issues). Six `docs/DECISIONS_LOG.md` entries dated 2026-08-18. |

## File Inventory — Phase 9 output (new)

| Path | Status | Description |
|------|--------|--------------|
| [services/api/Dockerfile](../services/api/Dockerfile) | Complete (new), **built + smoke-run** | Multi-stage: `builder` stage `pip wheel`s `requirements.txt` (including `packages/shared`'s editable local dep, converted to a real wheel — see decisions log) into `/wheels`; `runtime` stage installs only those wheels + `src/`, runs as non-root `appuser`, `HEALTHCHECK`s `/health/ready`. Verified: builds clean (555MB), `import src.main` succeeds in-container, a real `docker run` against this repo's own local Postgres/Qdrant/Redis produced a real `200` on `/health` and a real, correctly-`degraded` `503` on `/health/ready` (see header). |
| [services/ingestion/Dockerfile](../services/ingestion/Dockerfile) | Complete (new), **built + smoke-run** | Same two-stage shape; runtime stage additionally installs Ghostscript + `libgl1`/`libglib2.0-0` (camelot's real runtime deps, confirmed via `which gs` in-container). Runs the Celery worker with the default `prefork` pool — deliberately NOT `--pool=solo` (that's a Windows-only workaround, irrelevant on the Linux container; see decisions log). Verified: builds clean (594MB), `import src.infra.celery_app` succeeds in-container. Not run as a live worker against a real broker this phase (no managed Redis provisioned — see Known Issues). |
| [docker-compose.prod.yml](../docker-compose.prod.yml) | Complete (new), **syntax-validated** | Two services (`api`, `ingestion-worker`), no bind mounts, `restart: unless-stopped`, points at externally-managed Postgres/Qdrant/Redis via `.env.prod` rather than local containers — deliberately does not replicate `docker-compose.yml`'s local `postgres`/`qdrant`/`redis` blocks (see decisions log for why). `docker compose -f docker-compose.prod.yml config` resolved cleanly. Not run as `up` against real managed endpoints or against local containers via `host.docker.internal` end-to-end (the api Dockerfile itself was, directly via `docker run` — see header). |
| [.env.prod.example](../.env.prod.example) | Complete (new) | Documents every var `docker-compose.prod.yml` / `infra/terraform`'s ECS task definitions expect, in both their real-managed-endpoint and local-`host.docker.internal`-smoke-test shapes. Placeholders only, matching the repo-root `.env.example`'s existing convention. |
| [infra/terraform/main.tf](../infra/terraform/main.tf) | Complete (new), **`terraform init`/`validate`/`fmt`-verified, not `plan`/`apply`-verified** | RDS Postgres, ElastiCache Redis, two ECR repos, ECS (Fargate) cluster running `api` (behind an ALB, health-checked on `/health/ready` — the same endpoint the Dockerfile's own `HEALTHCHECK` uses) and `ingestion-worker` (no public endpoint) as independently-scaled services, IAM for task execution, SSM `SecureString` params for the four secrets rather than plaintext task-def env vars. Qdrant Cloud itself is NOT provisioned here (no official Terraform provider exists) — only its endpoint/key are consumed, passed through to both task definitions. |
| [infra/terraform/variables.tf](../infra/terraform/variables.tf) | Complete (new), **`terraform validate`-verified, not `plan`/`apply`-verified** | Every input `main.tf` needs — `db_password`/`qdrant_cloud_api_key`/`cohere_api_key`/`openai_api_key` marked `sensitive`, no default (must come from a gitignored `*.tfvars` or `TF_VAR_*`). Header comment flags the default-VPC/public-subnet simplification that applies throughout `main.tf`. |
| [infra/terraform/.terraform.lock.hcl](../infra/terraform/.terraform.lock.hcl) | Complete (new) | Real provider lock file produced by a real `terraform init -backend=false` (via the official `hashicorp/terraform` Docker image — see header) — locks `hashicorp/aws ~> 5.0` to `5.100.0`. Committed per Terraform's own convention (its `init` output says so explicitly), not a scratch file. |
| [.github/workflows/ci.yml](../.github/workflows/ci.yml) | Complete (new), **YAML-valid, never run in real GitHub Actions** | Six parallel jobs: `lint-{api,ingestion}`, `typecheck-{api,ingestion}`, `test-{api,ingestion}`. `test-api` provisions real Postgres/Qdrant/Redis `services:` containers (same pattern `eval-regression.yml` already established) and runs Alembic migrations before `pytest tests -v`; `test-ingestion` needs no live infra. Both `*-ingestion` jobs install Ghostscript via `apt-get` first. Triggers on every PR into `main` and every push to `main`. |
| [.github/workflows/cd-staging.yml](../.github/workflows/cd-staging.yml) | Complete (new), **YAML-valid, never run in real GitHub Actions** | On push to `main`: builds + pushes both Dockerfiles to ECR under two tags (commit SHA, and mutable `staging-latest`), then force-redeploys both ECS services and waits for `api` to stabilize. Uses OIDC (`role-to-assume`), not static AWS keys. Depends on repository secrets/variables (`AWS_DEPLOY_ROLE_ARN`, `ECR_API_REPOSITORY`, `ECR_INGESTION_REPOSITORY`, `ECS_CLUSTER`, `ECS_SERVICE_API`, `ECS_SERVICE_INGESTION`) that only exist once `infra/terraform` is actually applied and its outputs copied in — see decisions log. |

### Everything else (unchanged this phase)

| Area | Status |
|------|--------|
| `services/api/src`, `services/ingestion/src` | Unchanged — no application logic touched this phase. |
| `frontend` | Unchanged. Still no `tsconfig.json`, still no test suite — `ci.yml` deliberately has no frontend job this phase for that reason (see decisions log). |
| `eval/`, `.github/workflows/eval-regression.yml` | Unchanged. |
| `docs/architecture.md` | Unchanged — this phase's Terraform scaffold implements its §4, doesn't revise it. |
| `data/uploads/` | Gitignored, unchanged. |

## Known Issues / Bugs

**Carried over, unchanged this phase:** the full Phase 4–8 known-issues
list (unused shadcn components, disconnected dark-mode tokens, missing
aria-labels, no `GET /documents/{id}/file`, `GET /documents` not
tenant-filtered by design, `POST /documents`'s unguarded find-or-create
race, no dead-letter queue, heuristic document/table/footnote detection,
no streaming, no query/rerank caching, no `tsconfig.json`, `Layout.tsx`'s
`MOCK_PROJECTS`, the open `eval-007`/`eval-011` retrieval-quality finding,
every inspection-calibrated retrieval/confidence constant still
unvalidated against real eval data, `eval-regression.yml` never run in
real GitHub Actions, `LANGCHAIN_API_KEY` never supplied to any session,
the stray `ticker='AI'` data row) — see git history / Phase 8's own
snapshot for the full table, none fixed or newly introduced this phase.

**Phase 9-specific, all flagged inline in the files themselves and in
`docs/DECISIONS_LOG.md`, restated here for visibility:**

- **`infra/terraform` was `terraform validate`-clean but never `plan`/
  `apply`-verified against a real AWS account** — no AWS credentials
  supplied to this session. `terraform init`/`validate`/`fmt` all ran for
  real (via the official `hashicorp/terraform` Docker image, since the
  CLI isn't installed locally) and passed, which does catch real
  structural errors (a wrong attribute name, bad block nesting, an
  undeclared reference) — but `validate` cannot catch everything `plan`
  would: whether `container_definitions`' `jsonencode(...)` shape is
  something the ECS API actually accepts, whether `aws_lb_target_group`'s
  `target_type = "ip"` correctly pairs with the `awsvpc` network mode used
  above it, and any account-specific constraint (VPC quota, region
  availability of `db.t4g.micro`/`cache.t4g.micro`) all need a real `plan`
  against a real account to know for certain. That's the next real step,
  with real AWS credentials, which needs to be Sam's own action per
  `CLAUDE.md`'s "real secrets aren't typed into a session" convention.
- **`docker-compose.prod.yml` was not run as `up` end-to-end** — the api
  Dockerfile itself *was*, directly via `docker run` against local infra
  (see this file's own header) confirming the image works; the compose
  file's own orchestration (env-file wiring, healthcheck-based restart
  behavior, both services together) was only syntax-validated via
  `docker compose config`, not exercised live.
- **Neither `ci.yml` nor `cd-staging.yml` has run in real GitHub Actions**
  — same class of limitation as Phase 8's `eval-regression.yml`, now
  affecting two more workflow files for the same underlying reason (this
  session can't push to a branch/PR or configure repository
  secrets/variables).
- **`cd-staging.yml` depends on an IAM role (`AWS_DEPLOY_ROLE_ARN`) with
  an OIDC trust policy for this specific GitHub repo that `infra/terraform`
  does NOT provision** — a real, scoped gap for whenever this is actually
  deployed, not silently assumed away.
- **No autoscaling** on either ECS service — `api_desired_count`/
  `ingestion_desired_count` are fixed Terraform variables, despite
  `docs/architecture.md` §4 naming independent scaling as a deliberate
  design property of the two services. Flagged in `main.tf`'s own
  decisions-log entry as a real next step once there's real traffic to
  scale against.
- **RDS is configured for disposability, not durability**
  (`skip_final_snapshot = true`, 1-day backup retention) — correct for a
  throwaway staging environment, wrong for anything holding real data;
  flagged inline in `main.tf`.

**Grep for `TODO`/`FIXME`/`XXX`/`NotImplementedError`/bare `pass`:** No
matches in any file this phase added.

## Deviations From the Original Plan

- **AWS (RDS/ElastiCache/ECS-Fargate/ALB/ECR) was picked as the concrete
  cloud target for `infra/terraform`**, not left as pseudo-code covering
  multiple providers — `docs/architecture.md` §4 already names "ECS/Cloud
  Run" and "RDS/Cloud SQL" as the realistic pair of options; AWS was
  chosen so the whole stack (compute, DB, cache, load balancer, registry)
  comes from one provider rather than splitting across two clouds for a
  portfolio-scoped scaffold. Not a new item in `CLAUDE.md` §3's agreed
  stack (Docker + GitHub Actions was already agreed; Terraform + a cloud
  target is what the Phase 9 prompt itself asked for), flagged the same
  way Phase 5–8's own small additive/concretizing decisions were.
- **SSM Parameter Store `SecureString` params for secrets**, instead of
  plaintext ECS task-definition `environment` entries — a real hardening
  choice beyond the Phase 9 prompt's literal ask, made because plaintext
  task-def env vars are visible to anyone with task-definition read
  access; costs one extra IAM policy resource. See decisions log.
- Everything from the previous snapshot's deviations list (Phase 4's
  tenant-filtering/shared-corpus choice, Phase 5's provider decisions,
  Phase 6's `CitationResponse`/`get_or_create_actor` additions and the
  `numeric_verifier.py` bugfix, Phase 7's Compare/Admin scope pivots, and
  Phase 8's `ragas`/`langchain-community` version pin) still stands and
  wasn't touched this phase.

## Immediate Next Step

All nine phases in `PROJECT_HANDBOOK.md` §6 are now built. Real,
non-optional carry-overs for Sam, in priority order:

1. **Run `terraform plan`** with real AWS credentials — `init`/`validate`/
   `fmt` are already real and clean (see this file's own header); `plan`
   is the one remaining concrete step between "structurally valid HCL"
   and "known to actually apply." Do this before ever running
   `terraform apply` against a real account.
2. **Provision the Qdrant Cloud cluster manually** (Qdrant Cloud console —
   no Terraform provider exists) and feed its URL/API key into
   `terraform apply -var qdrant_cloud_url=... -var qdrant_cloud_api_key=...`.
3. **After a successful `apply`**, copy `terraform output`'s
   `ecr_api_repository_url`/`ecr_ingestion_repository_url`/
   `ecs_cluster_name` (plus the ECS service names) into this repo's GitHub
   Actions repository variables, and create the `AWS_DEPLOY_ROLE_ARN` OIDC
   role `cd-staging.yml` expects, so a real merge to `main` can actually
   deploy.
4. **Open a real PR** once repository secrets exist, to get `ci.yml`'s
   first real green run — the literal Definition of Done this phase's own
   prompt named.
5. Everything carried over from Phase 8 (the `eval-007`/`eval-011`
   retrieval-quality investigation, validating retrieval/confidence
   constants against real eval scores, a real LangSmith trace) remains
   open and is unaffected by this phase's deployment work.

With all nine phases done, the natural next arc is `PROJECT_HANDBOOK.md`
§8's portfolio-packaging pass — README, resume bullets carrying Phase 8's
real eval numbers, and rehearsing 3–4 `docs/DECISIONS_LOG.md` entries for
interview explanation — rather than a tenth implementation phase.
