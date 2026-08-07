# Decisions Log — Aegis Intelligence

This is the reasoning companion to the code. `docs/progress.md` says *what*
exists; this file says *why* it's built the way it is. Its purpose is to let
Sam explain any part of this project, cold, to an interviewer or reviewer —
so entries should read like a design-review note, not a commit message.

**Maintained by Claude Code.** An entry is appended here after every
implementation unit — a model, an endpoint, a pipeline stage, a nontrivial
fix — before that unit of work is considered done. See `CLAUDE.md` §5 for
the exact rule and `PROJECT_HANDBOOK.md` for the phase plan this maps to.

Entries are append-only, newest at the bottom, one per implementation unit.
Don't edit past entries to "clean them up" — if a decision was later
reversed, add a new entry that says so and links back to the old one; the
history of *why things changed* is itself useful context.

---

## Entry template

```markdown
## [YYYY-MM-DD] <short title of what was built>
**Phase:** <n — phase name>
**What was built:** <1-3 plain-language sentences>
**Why this approach:** <the actual reasoning - alternatives considered and
why this one won>
**Key concepts a reviewer should understand:** <bullets>
**Tradeoffs / deliberately left out:** <bullets>
**How it connects to the rest of the system:** <1-2 sentences>
```

---

<!-- Entries start below this line. Do not remove the line above. -->

## [2026-08-07] Service dependency manifests (setup/dependencies)
**Phase:** pre-work — not one of the nine build phases, no `docs/progress.md`
phase rows updated for this entry.
**What was built:** `services/api/requirements.txt` and
`services/ingestion/requirements.txt`, covering the two services' agreed
stacks (FastAPI + SQLAlchemy 2.0/Alembic + Postgres + Qdrant + Celery/Redis +
Cohere rerank for `api`; Celery/Redis + pymupdf + camelot + the same
DB/vector/rerank clients for `ingestion`), plus dev tooling (pytest, mypy,
ruff) in both.
**Why this approach:** Used loose `>=` pins rather than exact pins or a fully
locked file. At this stage there's no deployed environment, no CI matrix, and
no team to keep in sync — the risk a lockfile protects against (drift between
environments) doesn't exist yet, while exact pins would mean manually bumping
versions by hand every time a new dependency is added during early
scaffolding, which is most of the near-term work. The tradeoff is accepted:
once Phase 5+ (Celery/Docker) stabilizes and there's a real deployment
target, this should move to a locked file via `pip-compile` (or equivalent)
so builds become reproducible — flagging that now so it isn't forgotten.
**Key concepts a reviewer should understand:**
- `>=` pins express "compatible stack, latest is fine for now"; a lockfile
  (`pip-compile` output, `requirements.lock`, or similar) expresses "exactly
  this, reproducibly" — different tools for different project maturity.
- The two requirements files are intentionally not identical: `api` has no
  parsing libraries (pymupdf/camelot) since it never touches raw PDFs, and
  `ingestion` has no `fastapi`/`uvicorn` since it's a worker, not a web
  server. Both share the DB, vector store, and rerank clients because both
  need to read/write the same Postgres tables and Qdrant collections.
**Tradeoffs / deliberately left out:** No lockfile yet (see above). No
`requirements-dev.txt` split — dev tooling (pytest/mypy/ruff) is inline in
both files for now since each service is small; worth splitting out if the
list grows.
**How it connects to the rest of the system:** These are what
`pip install -r requirements.txt` inside each service's venv
(`services/api`, `services/ingestion` per `PROJECT_HANDBOOK.md` §5) will
install. Nothing depends on these files yet since no code has been written
in either service — this is pure setup ahead of Phase 1.

**Manual install flag (Windows):** `camelot-py[cv]` depends on Ghostscript
being installed at the OS level for PDF table extraction. Neither `pip`
nor `winget` installs this automatically — it must be installed manually
(e.g. from https://www.ghostscript.com/releases/gsdnld.html) and available
on `PATH` before `camelot-py` table extraction will work in
`services/ingestion`. Do not assume it's present; verify with
`gswin64c -v` (or `gswin32c -v` on 32-bit) before relying on camelot in a
task.

---

## [2026-08-07] Root env template, local infra compose file, .gitignore
(setup)
**Phase:** pre-work — not one of the nine build phases, no `docs/progress.md`
phase rows updated for this entry.
**What was built:** `.env.example` (placeholder values for `DATABASE_URL`,
`POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB`, `QDRANT_URL`, `REDIS_URL`,
`COHERE_API_KEY`, `EMBEDDING_API_KEY`), `docker-compose.yml` (postgres,
qdrant, redis — with named volumes so data survives `docker compose down`),
and a root `.gitignore` covering Python/Node build artifacts, `.env`, and a
few repo-specific paths (`eval/results/`, ad-hoc `scripts/` scratch files).
**Why this approach:** `docker-compose.yml` intentionally excludes `api` and
`ingestion` service entries even though both are named directories already.
Compose services that reference a `build:` context need a `Dockerfile` to
exist at that path, and neither service has one yet — those are built in
Phase 9 per `PROJECT_HANDBOOK.md`. Adding stub entries now would make
`docker compose up` fail outright (or silently do nothing useful) for every
dev running local infra between now and Phase 9, which is strictly worse
than the current state where those services just run from their venvs
per `PROJECT_HANDBOOK.md` §5.3 and reach Postgres/Qdrant/Redis over the
host-mapped ports. A comment in the file itself flags this so a future
pass doesn't "fix" it by adding them early.
`EMBEDDING_API_KEY` is a placeholder name, not tied to a specific vendor
(OpenAI/Voyage/etc.) — that choice isn't made yet per
`PROJECT_HANDBOOK.md`'s `embedding/` stage, and a generic key name avoids
implying a decision that hasn't happened.
**Key concepts a reviewer should understand:**
- `.env.example` is checked in and must never hold real values — it's the
  contract for what a `.env` needs to contain, not a secrets store.
  `.env` itself is git-ignored (see below); `Copy-Item .env.example .env`
  per `PROJECT_HANDBOOK.md` §5.5 is how a dev gets a real, gitignored copy.
- Named volumes (`postgres_data`, `qdrant_data`, `redis_data`) instead of
  bind mounts: survives `docker compose down` (only `-v` drops them),
  and keeps container-internal data paths out of the host filesystem/repo.
- `POSTGRES_*` env vars in `docker-compose.yml` read from the shell/`.env`
  via `${VAR:-default}` syntax, with `changeme` as a fallback default so
  `docker compose up` doesn't hard-fail if `.env` hasn't been created yet
  — though real usage should always go through a filled-in `.env`.
**Tradeoffs / deliberately left out:** No `api`/`ingestion` compose
services (see above, by design until Phase 9). No `docker-compose.prod.yml`
yet — that's also Phase 9 per `PROJECT_HANDBOOK.md` §"Nine-Phase Plan".
No healthchecks on `qdrant`/`redis` (only `postgres` has one) — acceptable
for now since nothing depends on compose-level health gating yet; worth
adding once a service actually waits on these at startup.
**How it connects to the rest of the system:** `docker-compose.yml` is what
`PROJECT_HANDBOOK.md` §5.5 (`docker compose up -d`) stands up before any
phase work begins. `.env` (from `.env.example`) is read by both services'
`pydantic-settings`-based config once that code exists (Phase 2+). Confirmed
`.env` is covered by `.gitignore` (`.env` and `.env.*`, with an explicit
`!.env.example` exception) so no real secret can be committed by accident.

---

## [2026-08-07] Qdrant host port moved to 6335 (setup)
**Phase:** pre-work — not one of the nine build phases, no `docs/progress.md`
phase rows updated for this entry.
**What was built:** `docker-compose.yml`'s `qdrant` service now maps host
port `6335` to the container's internal port `6333` (`"6335:6333"`), instead
of `"6333:6333"`. `.env.example`'s `QDRANT_URL` placeholder updated to
`http://localhost:6335` to match.
**Why this approach:** Host port 6333 is already bound by an unrelated
Docker container from a different local project on this machine — not a
conflict within this repo's own config, and not a bug in Qdrant or in how
this project uses it. Remapping only the host side (`6335:6333`) is the
minimal fix: the container's internal port stays `6333` (Qdrant's default,
matches its own docs/tooling expectations), so nothing about how Qdrant
itself is configured or addressed *inside* Docker changes — only how the
host reaches it from outside. The alternative (freeing port 6333 by
stopping the other project's container) was rejected since it's an
unrelated project this repo shouldn't have opinions about.
**Key concepts a reviewer should understand:** Docker's `"host:container"`
port syntax means the two sides are independent — the container-internal
port only has to be consistent with what the service inside listens on
(Qdrant on `6333`), while the host-side port only has to be free on the
host machine and consistent with whatever's dialing in from outside Docker
(here, `QDRANT_URL` in `.env`/`.env.example`).
**Tradeoffs / deliberately left out:** This is a machine-local port choice,
not a portable convention — another dev's machine might not have this
collision at all, or might have a different one. If port collisions become
a recurring annoyance across the team, worth revisiting with a `.env`-driven
host port (e.g. `${QDRANT_HOST_PORT:-6335}:6333`) instead of a hardcoded
value in `docker-compose.yml`; not doing that now since it's a one-person,
one-machine setup at this stage.
**How it connects to the rest of the system:** Anything that talks to
Qdrant from outside Docker (initially just dev tooling/scripts; later
`services/api` and `services/ingestion` once their embedding/retrieval code
exists) reads `QDRANT_URL` from `.env` — confirmed `.env` on this machine
already had `6335` set correctly, so no functional change there, only
`docker-compose.yml` and the committed `.env.example` template needed
updating to stay consistent with it.

---

## [2026-08-07] Qdrant gRPC host port moved to 6336 (setup, cont.)
**Phase:** pre-work — not one of the nine build phases, no `docs/progress.md`
phase rows updated for this entry.
**What was built:** Second half of the same fix as the previous entry, not
a new issue. Qdrant's gRPC port (`6334`) is now mapped `"6336:6334"` in
`docker-compose.yml` instead of straight through — it hit the same host-port
collision with the same unrelated local Docker container that the REST port
(`6333`) did. `.env.example` gains `QDRANT_GRPC_URL=http://localhost:6336`
(didn't exist before; added now since this is the first place gRPC is
referenced at all).
**Why this approach:** Same reasoning as the REST-port fix — remap only the
host side, leave the container's internal port at Qdrant's default (`6334`)
so nothing about Qdrant's own config changes, only how the host reaches it.
`6336` was picked to sit next to `6335` (the REST remap) rather than
choosing an unrelated number, so the two host ports read as a pair.
**Key concepts a reviewer should understand:** Qdrant exposes both a REST
API (`6333`) and a gRPC API (`6334`) on separate ports; most current tooling
in this project only needs REST (`QDRANT_URL`), but `QDRANT_GRPC_URL` is
added now so it's available if/when `qdrant-client`'s gRPC mode is used
later (e.g. for lower-latency bulk upserts during ingestion) without another
port-collision surprise at that point.
**Tradeoffs / deliberately left out:** Same caveat as the REST fix — this is
a machine-local port choice, not a portable convention. If this keeps
recurring, both ports should move to `.env`-driven `${QDRANT_HOST_PORT:-...}`
/ `${QDRANT_GRPC_HOST_PORT:-...}` values in `docker-compose.yml` rather than
hardcoded numbers.
**How it connects to the rest of the system:** No functional code depends on
`QDRANT_GRPC_URL` yet — it's added preemptively alongside `QDRANT_URL` so
the env contract is complete before anything needs it, avoiding a second
scramble later. `.env` on this machine should be updated by hand to add the
same line (not done here — `.env` is gitignored and machine-local, out of
scope for this fix).
