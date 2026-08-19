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

---

## [2026-08-07] Fix undefined `Search` reference in Chat.tsx (Phase 1)
**Phase:** 1 — Fix the Chat.tsx crash
**What was built:** Changed the icon usage at
[Chat.tsx:70](../frontend/src/app/pages/Chat.tsx#L70) from `<Search .../>`
to `<SearchIcon .../>`, matching the actual import at
[Chat.tsx:230](../frontend/src/app/pages/Chat.tsx#L230)
(`import { Database, Search as SearchIcon } from 'lucide-react'`). No other
logic in the file touched.
**Why this approach:** The import already aliases `Search` to `SearchIcon`
— there's no unaliased `Search` binding anywhere in the file's scope, so
the only two ways to fix this were (a) rename the import to drop the alias,
or (b) rename the JSX usage to match the alias. Went with (b), the usage
site, since the alias is presumably intentional (avoids shadowing a DOM
global or another `Search`-named symbol elsewhere in the component tree)
and the task explicitly scoped the fix to "use the correctly imported
icon" rather than changing imports.
**Key concepts a reviewer should understand:**
- This was a plain `ReferenceError` at render time, not a TypeScript
  compile error — the Figma-exported `frontend/` has no `tsconfig.json`
  yet (tracked separately in `docs/progress.md`'s Known Issues), so nothing
  caught an undefined JSX identifier before runtime. Once a `tsconfig.json`
  exists, `noUnusedLocals`/strict JSX checks would have caught this class
  of bug at build time instead of only when a user hits the empty-project
  Chat view.
- `Database` (also imported at line 230) was already used correctly at
  line 49 — confirmed via grep before editing so the fix touched only the
  actually-broken reference.
**Tradeoffs / deliberately left out:** Did not consolidate the two
`lucide-react` import statements (lines 3 and 230) into one, and did not
move the line-230 import to the top of the file with the others — both
would be a real cleanup but count as "changing other logic/structure,"
which the task explicitly excluded. Worth a follow-up pass once more of
the frontend is being touched.
**How it connects to the rest of the system:** This unblocks
`activeProject.isEmpty` rendering in `Chat.tsx`, which every project starts
in until a document is ingested (Phase 4+) — without this fix the app
crashed on first load for any new/empty project, which is the very first
screen an interviewer or reviewer would hit.

---

## [2026-08-07] `docs/architecture.md` added — ER model now has a source of truth
**Phase:** pre-work for Phase 2 — not one of the nine build phases.
**What was built:** Nothing code-wise. Sam supplied `docs/architecture.md`
(system flow, decision/failure tables, deployment diagram, the §7 ER
diagram, and §8 use-case diagrams), which did not exist in the repo before
this point.
**Why this approach:** Phase 2's brief (`PROJECT_HANDBOOK.md`) instructs
implementing "the 11 entities in the ER model in `docs/architecture.md`
§7" — but `docs/progress.md`'s last snapshot explicitly confirmed
`docs/` had no architecture doc at all. Per `CLAUDE.md` §4 ("deviate from
the ER model... stop and ask first" / "if the ER model has a real gap, say
so explicitly") this was flagged back to Sam rather than inventing a
schema and silently presenting it as "the" ER model. Sam provided the real
document, which is now the authoritative source for every model built in
this phase.
**Key concepts a reviewer should understand:**
- The ER diagram's cardinality syntax (`||--o{`, `||--o|`, `||--||`) maps
  directly to SQLAlchemy `relationship()` shape decisions made in the
  entries below — e.g. `DOCUMENTCHUNK ||--o| TABLEDATA` (zero-or-one) is
  why `TableData.chunk_id` is unique instead of just indexed.
**Tradeoffs / deliberately left out:** Two implementation-level gaps
between the pasted ER diagram and what later phases will need are noted
inline in the entity-specific entries below (a `Document.status` column for
Phase 4's ingestion-pending state, and a `chunk_index` column on
`DocumentChunk` added now rather than deferred) rather than silently
invented or silently ignored.
**How it connects to the rest of the system:** Every model file from this
point on cites this document by section (`architecture.md §7`) instead of
restating the ER model from memory.

---

## [2026-08-07] `base.py` + `enums.py` — declarative base, naming convention, domain enums
**Phase:** 2 — DB schema (SQLAlchemy 2.0 models)
**What was built:** `services/api/src/models/db/base.py` (a `Base`
`DeclarativeBase` subclass carrying a shared `MetaData` naming convention)
and `enums.py` (`DocumentType`, `ChunkType`, `UserRole`, `OrgTier` — all
`str`-subclassed `enum.Enum`s), the first two files in the fixed build
order from `CLAUDE.md` §3.
**Why this approach:** The naming convention is applied once, at the
`MetaData` level, rather than passing an explicit `name=` to every
constraint in every model — Alembic autogenerate needs deterministic
constraint names to produce stable diffs (see inline docstring in
`base.py`), and doing it centrally means no model file can forget it.
For the enums, `str, enum.Enum` (not a bare `enum.Enum`) was chosen so a
value serializes as its plain string (`"form_10k"`) in Pydantic
schemas/JSON in later phases without an explicit `.value` at every call
site — the ergonomic cost of a bare `Enum` (constantly writing `.value`)
outweighs the marginal type-safety difference for this project's size.
Each enum maps to a native Postgres `ENUM` type (via SQLAlchemy's `Enum`,
wired up per-model in the entries below) rather than a `String` +
app-level `CHECK`/validation, so an invalid value is rejected at the
database layer, not just caught by whichever code path happens to
validate it.
**Key concepts a reviewer should understand:**
- `DeclarativeBase` (SQLAlchemy 2.0) replaces the old
  `declarative_base()` factory function — it's a real class other model
  base classes subclass, which is what lets `Mapped[...]`/`mapped_column`
  type-check correctly instead of relying on `Any`-typed legacy
  `Column(...)` declarations.
- `UserRole` only has `ANALYST`/`ADMIN` because those are the only two
  human actors in `architecture.md` §8's use-case diagrams — the
  "Scheduler" actor there is a cron/system trigger, not a `User` row.
- `DocumentType` splits 10-K and 10-Q into separate values (not one
  generic "filing") because they need different downstream section-parsing
  rules in Phase 5's `document_classifier.py`.
**Tradeoffs / deliberately left out:** Postgres `ENUM` types are not
append-only — adding a fifth `DocumentType` later requires a real
migration (`ALTER TYPE ... ADD VALUE`), unlike a `String` column. Accepted
because these four value sets are stable domain concepts, not
expected-to-grow lookup data; if that assumption breaks, the fix is a
migration, not a redesign.
**How it connects to the rest of the system:** Every one of the other 11
model files imports `Base` from `base.py` (it's the root of the
inheritance chain) and, where relevant, an enum from `enums.py` for its
enum-typed column. `models/db/__init__.py` (written later in this phase)
re-exports both alongside all 11 entity classes as the single import
surface Alembic's `env.py` and, eventually, `api/v1/deps.py` use.

---

## [2026-08-07] `organization.py` + `user.py` — tenancy root and its members
**Phase:** 2 — DB schema (SQLAlchemy 2.0 models)
**What was built:** `Organization` (`org_id`, `name`, `tier`) and `User`
(`user_id`, `org_id` FK, `name`, `email`, `role`), matching
`architecture.md` §7's `ORGANIZATION ||--o{ USER` exactly, plus the
`users`/`organization` relationship pair.
**Why this approach:** `User.org_id` uses `ondelete="CASCADE"` — deleting
an organization deletes its users outright, rather than orphaning them or
blocking the delete. This is the one place in the schema where a hard
tenant-offboarding delete is the *intended* behavior (contrast with
`Citation.chunk_id` later in this phase, which deliberately does the
opposite for audit-trail reasons). `email` gets `unique=True` even though
the pasted ER diagram doesn't mark it as such — the diagram documents
entities/relationships/cardinality, not column-level constraints, and a
user-identifying field that isn't unique can't safely back auth in Phase
3+; this is an implementation detail within the model, not a deviation
from the ER model's structure, so it didn't need a check-in per `CLAUDE.md`
§4.
**Key concepts a reviewer should understand:**
- The import direction is deliberate: `user.py` does a normal top-level
  `from src.models.db.organization import Organization` (safe — Organization
  never imports User at runtime), while `organization.py` only imports
  `User` under `TYPE_CHECKING`. If both did normal imports, Python would
  hit a circular-import error the moment either module was loaded. This
  same rule (parent imports child only under `TYPE_CHECKING`; child imports
  parent normally) repeats for every FK relationship in this phase, which
  is also *why* `CLAUDE.md`'s fixed build order is a real constraint and
  not just a style preference — it's the order that keeps this graph
  acyclic.
- `Mapped["Conversation"]` type-checks and resolves at runtime purely via
  SQLAlchemy's declarative class registry (matching on class name), not
  via the module's own import namespace — this is what makes the
  `TYPE_CHECKING`-only import safe instead of a `NameError` waiting to
  happen the first time a mapper configures.
**Tradeoffs / deliberately left out:** No `created_at`/`updated_at` audit
columns on either table — not in the pasted ER diagram, and adding
speculative columns beyond what's specified is exactly the kind of
schema deviation `CLAUDE.md` §4 asks to flag rather than do silently.
Worth revisiting once auth/audit logging is actually designed.
**How it connects to the rest of the system:** `Organization` is the root
every tenant-scoped query in Phase 3's API will filter through (via a
user's `org_id`); `User.conversations` is the entry point `conversation.py`
(built next-but-one in this phase) hangs off of.

---

## [2026-08-07] `company.py` + `document.py` — the filer and the filing
**Phase:** 2 — DB schema (SQLAlchemy 2.0 models)
**What was built:** `Company` (`company_id`, `ticker`, `name`, `sector`)
and `Document` (`document_id`, `company_id` FK, `document_type`,
`fiscal_quarter`, `fiscal_year`, `upload_date`, `source_url`), matching
`architecture.md` §7's `COMPANY ||--o{ DOCUMENT` exactly.
**Why this approach:** `fiscal_quarter` is `int | None` with a `CHECK
(fiscal_quarter IS NULL OR fiscal_quarter BETWEEN 1 AND 4)` — a 10-K
covers a full fiscal year and has no single quarter, so forcing it
non-null would mean every 10-K row lies about which quarter it's "for".
The `CHECK` constraint (rather than trusting app code to only ever write
1–4) is a deliberate small instance of this project's larger "verify at
the source, don't trust the caller" theme, applied to the schema itself.
`ticker` gets `unique=True` for the same reason `User.email` did in the
previous entry — an implementation-level constraint, not an ER-model
deviation.
**Key concepts a reviewer should understand:**
- **Flagged gap, not silently added:** `architecture.md` §1 step 1 says
  ingestion "creates a `Document` record with status `pending`" and
  enqueues a Celery task, but the pasted §7 ER diagram's `DOCUMENT` entity
  has no `status` field. Rather than either (a) inventing a `status`
  column not in the authoritative diagram, or (b) silently ignoring a
  requirement `architecture.md` states elsewhere, this is left out now and
  flagged here: Phase 4 (`PROJECT_HANDBOOK.md`'s "Wire the Library page"),
  which is the phase that actually needs a pending/processing/complete
  document lifecycle, should add it as an additive column via its own
  migration — which `CLAUDE.md` §4 explicitly allows without a check-in
  ("a new column is usually fine").
- `company_id`'s FK uses `ondelete="CASCADE"` — deleting a `Company`
  deletes all its `Document`s. Companies are low-churn reference data
  (ticker/name/sector), so this is a low-risk default; revisit if
  companies ever need a "deactivate but keep historical filings" path.
**Tradeoffs / deliberately left out:** No `status` column (see above, by
design, not by oversight). No `title`/`filename` display fields either —
not in the ER diagram, and the frontend's `Library.tsx` mock data that
will eventually need them is Phase 4's concern.
**How it connects to the rest of the system:** `Document.chunks` is what
`document_chunk.py` (next in this phase) hangs off of; `document_type`
drives which parsing path Phase 5's `document_classifier.py` routes a file
through.

---

## [2026-08-07] `document_chunk.py` + `table_data.py` — the retrieval unit and its structured tables
**Phase:** 2 — DB schema (SQLAlchemy 2.0 models)
**What was built:** `DocumentChunk` (`chunk_id`, `document_id` FK,
`chunk_type`, `content`, `page_number`, `chunk_index`,
`embedding_vector_id`) and `TableData` (`table_id`, `chunk_id` FK,
`raw_table_json`, `row_count`, `column_count`), matching
`architecture.md` §7's `DOCUMENT ||--o{ DOCUMENTCHUNK`,
`DOCUMENTCHUNK ||--o| TABLEDATA`, and `DOCUMENTCHUNK ||--o{ CITATION`.
**Why this approach — the one deliberate addition beyond the pasted ER
diagram:** `chunk_index` is **not** a column in `architecture.md` §7's
`DOCUMENTCHUNK` entity, but it's added here anyway, with a
`UniqueConstraint(document_id, page_number, chunk_index)`. Two things
independently pointed at the same gap: (1) `CLAUDE.md` §5's own entry
template names "what the `UniqueConstraint` on `(document_id, page_number,
chunk_index)` buys us here" as its worked example for this exact table,
and (2) `architecture.md` §2 explicitly requires re-ingestion to be
idempotent ("re-running ingestion on the same document should overwrite,
not duplicate") — which needs *some* deterministic ordinal key to upsert
against, and without one, two chunks on the same page (there will usually
be several — narrative + footnote + maybe a table, on one page) are
otherwise indistinguishable at the schema level. This is flagged here
explicitly rather than silently added: it's a purely additive column (no
existing data, no rename/drop of anything in the pasted diagram), which
`CLAUDE.md` §4 treats as the low-risk case, but Sam should sanity-check
the reasoning above rather than discover the discrepancy later.
**Key concepts a reviewer should understand:**
- `TableData.chunk_id` is `unique=True`, not just a plain indexed FK —
  that's what turns the ER diagram's `||--o|` ("zero-or-one") cardinality
  into an actual database-enforced invariant instead of an
  application-trusted convention. `chunk.table_data` is typed
  `TableData | None` and `relationship(..., uselist=False)` to match.
- `raw_table_json` uses Postgres `JSONB`, not `JSON` — binary storage
  supports containment/path queries later without a migration, and tables
  are write-once/read-many so the (small) extra write cost JSONB imposes
  vs. plain JSON is the right side of that tradeoff here.
- `embedding_vector_id` is nullable *and* unique: nullable because the
  Postgres row can exist slightly before the Qdrant upsert completes in
  Phase 5's ingestion task (two systems, two separate writes); unique
  because the join is meant to be 1:1 — a duplicate value would mean two
  chunks silently pointing at the same vector, which numeric verification
  (Phase 6) depends on not happening.
**Tradeoffs / deliberately left out:** `citations` on `DocumentChunk` has
no `cascade` argument (unlike every other parent relationship in this
phase) — that's intentional and explained fully in the `citation.py` entry
later in this phase; flagging here so the asymmetry doesn't look like an
oversight when reading this file top to bottom.
**How it connects to the rest of the system:** `chunk_id` +
`page_number`/`chunk_index` together are the Postgres half of the
`source_location` concept from `architecture.md` §2/§3 — the Qdrant half
is `embedding_vector_id`. `citation.py` (later this phase) FKs to
`chunk_id` directly, which is what lets a citation object point at
something real instead of a re-derived, potentially-stale reference.

---

## [2026-08-07] `conversation.py` + `query.py` — chat threads and the questions inside them
**Phase:** 2 — DB schema (SQLAlchemy 2.0 models)
**What was built:** `Conversation` (`conversation_id`, `user_id` FK,
`started_at`) and `Query` (`query_id`, `conversation_id` FK, `query_text`,
`reformulated_query_text`, `created_at`), matching `architecture.md` §7's
`USER ||--o{ CONVERSATION` and `CONVERSATION ||--o{ QUERY` exactly.
**Why this approach:** `Conversation.queries` is declared with
`order_by="Query.created_at"` — a string expression rather than a real
reference to `Query.created_at`, since `Query` isn't safely importable at
runtime here (it would create the same cycle the whole `TYPE_CHECKING`
pattern in this phase exists to avoid). This isn't just cosmetic ordering:
Phase 6's history-aware reformulation needs to walk a conversation's
questions in the order they were actually asked to build correct context,
and leaving ordering to "whatever order Postgres happens to return rows
in" would be a latent bug waiting for the day insertion order and primary
key order diverge (e.g. after a future bulk-import script).
**Key concepts a reviewer should understand:**
- `Query.answer` and `Query.eval_result` are both typed `X | None` with
  `uselist=False` — same 1:1-via-FK-uniqueness pattern as
  `TableData.chunk_id` two entries back, this time expressing
  `QUERY ||--|| ANSWER` (always exactly one, once generation completes)
  and `QUERY ||--o| EVALRESULT` (zero until the eval suite has scored it,
  per `architecture.md`'s cardinality note under the diagram) with the
  same mechanism but different real-world nullability.
- Table name is `queries`, not `query` — purely to avoid reading
  awkwardly next to SQLAlchemy's own `Session.query()`, documented inline
  since it's the one table name in this schema that isn't just the
  obvious pluralization of the entity name.
**Tradeoffs / deliberately left out:** No soft-delete/retention field on
`Conversation` even though `architecture.md` §8's Admin use-case diagram
lists "Configure retention & access" as a capability — that's an Admin
*feature* to build later (Phase 7), not a schema requirement yet; adding a
speculative `retention_expires_at` column now with no code that reads it
would be exactly the kind of ER-model deviation this phase is trying to
avoid making casually.
**How it connects to the rest of the system:** `Conversation` is what
Phase 3's `POST /query`/`POST /query/followup` routes create/append to;
`Query.reformulated_query_text` is what Phase 6's hybrid retrieval
actually searches against when it's populated, versus `query_text` when
it's a fresh question.

---

## [2026-08-07] `answer.py` + `citation.py` + `eval_result.py` — the response, its evidence, and its score
**Phase:** 2 — DB schema (SQLAlchemy 2.0 models)
**What was built:** The last three entities: `Answer` (`answer_id`,
`query_id` FK, `answer_text`, `confidence_score`, `generated_at`),
`Citation` (`citation_id`, `answer_id` FK, `chunk_id` FK, `exact_location`,
`snippet`), and `EvalResult` (`eval_id`, `query_id` FK,
`retrieval_precision`, `groundedness_score`, `flagged_by_human`) —
completing `architecture.md` §7's `QUERY ||--|| ANSWER`,
`ANSWER ||--o{ CITATION`, `DOCUMENTCHUNK ||--o{ CITATION`, and
`QUERY ||--o| EVALRESULT`. All 11 entities from the ER diagram now exist.
**Why this approach — the most deliberate FK decision in the whole
schema:** `Citation.chunk_id` has **no** `ondelete="CASCADE"` (Postgres's
default `NO ACTION` applies, which behaves like `RESTRICT` inside a
transaction). Every other FK in this phase cascades, because in every
other case the child genuinely has no meaning without its parent (a
`TableData` row with no chunk, a `Conversation` with no user). `Citation`
is different: it's an audit record of evidence *that was actually shown to
a user*. If a document gets re-ingested and its old chunks physically
deleted, cascading the delete down to `Citation` would silently erase the
historical record of what evidence a past answer was based on — directly
undermining this project's core "numeric traceability" promise
(`CLAUDE.md` §1). Making the FK non-cascading forces whatever Phase 5
re-ingestion logic ends up deleting old chunks to either (a) leave cited
chunks in place, or (b) soft-delete/version them instead of a hard
`DELETE` — a decision Phase 5 now has to make on purpose, not one this
schema quietly foreclosed by picking `CASCADE` everywhere out of
consistency. `Citation.snippet`/`exact_location` being copied onto the
row (not looked up live via the FK) means the citation stays
human-readable even in the (should-be-rare) case a chunk is later removed
by an explicit, deliberate operation.
**Key concepts a reviewer should understand:**
- `confidence_score`, `retrieval_precision`, and `groundedness_score` all
  get a `CHECK (x >= 0 AND x <= 1)` — same "verify at the schema layer"
  pattern as `Document.fiscal_quarter`'s range check earlier in this
  phase, applied to the numeric scores this project's eval story
  (`CLAUDE.md` §1, item 2) is built around.
- `EvalResult` is populated by Phase 8's offline `ragas_runner.py`, not by
  the live query pipeline — most `Query` rows will never get one, which is
  exactly what the `||--o|` (zero-or-one) cardinality and the nullable
  `Query.eval_result` relationship express.
- `Citation` is the one entity with two FKs to two different parents
  (`Answer` and `DocumentChunk`) rather than one — both imports are
  normal top-level imports (not `TYPE_CHECKING`-gated) because both
  `answer.py` and `document_chunk.py` were built earlier in the fixed
  order and neither imports `citation.py` back, so there's no cycle to
  break.
**Tradeoffs / deliberately left out:** No explicit index/constraint
enforcing "an `Answer`'s citations must reference chunks belonging to
documents the querying user's org actually has access to" — that's a
row-level authorization concern for Phase 3's tenant-context middleware to
enforce at the query layer, not something a foreign key can express.
**How it connects to the rest of the system:** This closes out the ER
model — `Answer`/`Citation` are what Phase 6's `citation_resolver.py`
writes after generation, and `EvalResult` is what Phase 8's CI eval gate
reads to fail a workflow run when scores regress. With all 11 entities in
place, `models/db/__init__.py` (next) becomes the single import surface
everything downstream (Alembic, then Phase 3's `deps.py`) depends on.

---

## [2026-08-07] Model-layer unit tests (`tests/unit/conftest.py` + `test_models.py`)
**Phase:** 2 — DB schema (SQLAlchemy 2.0 models), continued
**What was built:** `services/api/tests/unit/conftest.py` (an `engine`
fixture + a `db_session` fixture that wraps each test in an outer
transaction, always rolled back, never committed) and `test_models.py`
(three tests), plus `services/api/pyproject.toml` (`[tool.pytest.ini_options]`
with `pythonpath = ["."]` — needed so `import src.models.db` resolves when
pytest is invoked as `pytest tests\unit -v` from `services/api`, since
pytest's default import mode otherwise adds `tests/unit` itself, not
`services/api`, to `sys.path`).
**This goes beyond the original plan, on purpose, not silently:**
`docs/Financial_RAG_Project_Structure.md`'s planned `services/api/tests/
unit/` only lists `test_rrf.py`, `test_reranker.py`, and
`test_numeric_verifier.py` — all Phase 6 retrieval-logic tests. No model-
layer test file was planned for Phase 2 at all. This entry exists so that
gap is visible and explained rather than just quietly filled: Sam asked
for model-layer tests as a deliberate rigor addition partway through
Phase 2, not because the original structure doc was wrong, but because by
the time all 11 models existed, three of them encoded real design
decisions (see below) that only a real test — not a read of the code —
actually confirms hold.
**Why this approach — Postgres, not SQLite:** The fixture connects to the
real `docker-compose.yml` Postgres, never SQLite, even though SQLite is
the more common "fast unit test" default. Every one of these models uses
at least one Postgres-native type (`UUID`, `JSONB`, `ENUM` via
`sqlalchemy.Enum`) that SQLite either doesn't have or silently
downgrades/emulates loosely (e.g. SQLite has no real `ENUM` type and
won't enforce it at the column level the way Postgres does). More
fundamentally, all three behaviors these tests check — a composite
`UniqueConstraint`, immediate (non-deferred) foreign-key enforcement on
`DELETE`, and `IntegrityError` semantics — are database-enforced
behaviors, not ORM behaviors. Testing them against SQLite would be
testing SQLite's constraint enforcement, not Postgres's, and this
project's whole premise (`CLAUDE.md` §1: "every number in an answer must
be verified against the actual source table") is exactly the kind of
project where "the test passed against a different database than
production uses" is not an acceptable gap. The `db_session` fixture's
`join_transaction_mode="create_savepoint"` (SQLAlchemy 2.0's supported
"external transaction" pattern) is what makes this fast and side-effect-
free despite hitting a real database: each test's `session.commit()`
calls only release/reopen a `SAVEPOINT` nested inside a transaction the
fixture always rolls back, so nothing a test does — including the
constraint violations these tests deliberately trigger — ever persists or
needs manual cleanup.
**Why these three specific behaviors, not broader CRUD coverage:** Each
one encodes a decision from an earlier entry in this file that would fail
*silently* if it regressed — a broken constraint doesn't raise a Python
exception on its own, code just quietly stops enforcing an invariant:
- `DocumentChunk`'s `(document_id, page_number, chunk_index)` uniqueness
  is the mechanism the idempotent re-ingestion guarantee in
  `architecture.md` §2 depends on, and `chunk_index` itself was an
  addition beyond the pasted ER diagram (see the `document_chunk.py`
  entry) — untested, a typo in the constraint's column list or a future
  "simplification" that drops it would go unnoticed until Phase 5's
  re-ingestion logic actually duplicated rows in production.
- `Citation` resolving both its `answer` and `chunk` relationships is the
  entire reason the entity exists (`source_location`, `architecture.md`
  §2/§3) — untested, a `back_populates` typo or a wrong FK target would
  still let the ORM define the class without error, just silently return
  `None`/empty lists at read time.
- `Citation.chunk_id`'s missing `ondelete="CASCADE"` is the one FK in the
  whole schema that's an exception to the pattern every other FK follows
  (see the `answer.py`/`citation.py`/`eval_result.py` entry) — exactly
  the kind of one-off that a future contributor "cleaning up
  inconsistent FK behavior" could plausibly undo without realizing it
  was deliberate. A test that fails loudly if that ever happens is worth
  more here than a code comment alone.
**Tradeoffs / deliberately left out:** No coverage yet for the other 8
entities' basic construction/persistence, and no coverage for
`OrgTier`/`DocumentType`/`ChunkType`/`UserRole` enum round-tripping —
those are lower-risk (a broken basic insert would fail loudly the first
time any downstream code touched that table, unlike the three silent-
failure-mode behaviors above) and are reasonable to add incrementally as
Phase 3+ actually starts exercising those tables, rather than write
speculative coverage now. `db_session`'s `engine` fixture assumes the
Postgres from `docker-compose.yml` is already running (`docker compose up
-d`) — no test-time check-and-fail-with-a-clear-message if it isn't; a
raw `psycopg2.OperationalError` on the first test is the current failure
mode, acceptable for now given this is local dev tooling, not CI (Phase
9's `ci.yml` will need a Postgres service container regardless, which is
a separate concern from this fixture).
**How it connects to the rest of the system:** These tests exercise
exactly the model layer built earlier in this phase and nothing else
(no API, no ingestion) — they're the first thing in the repo that runs
against the real Postgres schema rather than just generating/applying a
migration against it. `PROJECT_HANDBOOK.md`'s Phase 2 "What gets built"
line was updated to list both new files so the handbook accurately
reflects that model-layer tests now start in Phase 2, not Phase 6.

---

## [2026-08-08] FastAPI skeleton — `main.py`, six stub routers, `deps.py`, three middleware stubs, response schemas
**Phase:** 3 — FastAPI skeleton with stub endpoints
**What was built:** the full API surface with zero business logic behind
it. `models/schemas/{query,document,conversation,citation,admin,health}.py`
— typed Pydantic request/response models for every planned endpoint.
`api/v1/deps.py` — `get_db` (yields a request-scoped `Session` from Phase
2's `SessionLocal`, always closed) and `get_tenant_context` (reads a
`TenantContext` dataclass off `request.state`, defaulting to a
placeholder). `api/middleware/{auth,tenant_context,rate_limit}.py` —
three `BaseHTTPMiddleware` subclasses that establish the request-handling
shape (extract a bearer token, resolve an org from a header, pass
through) without verifying or limiting anything for real yet.
`api/v1/routes/{query,documents,conversations,citations,health,admin}.py`
— eleven endpoints total (`POST /query`, `POST /query/followup`,
`GET/POST /documents`, `GET /conversations`, `GET /conversations/{id}`,
`GET /citations/{id}`, `GET /admin/analytics`,
`GET /admin/flagged-answers`, `GET /health`, `GET /health/ready`), each
depending on `get_db`/`get_tenant_context` and returning typed
placeholder data. `main.py` — the app factory that registers all of it.
**Why this approach:**
- **Schemas mirror the ORM models field-for-field where a route maps 1:1
  onto an entity** (`DocumentResponse` vs. `Document`, `CitationResponse`
  vs. `Citation`), with `model_config = ConfigDict(from_attributes=True)`
  set now even though no route queries the DB yet — so Phase 4/6 can
  return an ORM instance directly from a route and have FastAPI serialize
  it, instead of hand-mapping attributes later. `QueryResponse` is the one
  schema that's a genuine composition (`Query` + `Answer` +
  `list[Citation]`), because that's what Phase 6's pipeline actually
  produces — no single ORM model maps onto "the answer to a question."
- **`DocumentResponse` deliberately omits `status`**, even though
  `architecture.md` §1 describes documents having one — carrying forward
  Phase 2's decision to leave `Document.status` off the ORM model until
  Phase 4. A schema is not the place to invent a field the database can't
  yet store; that would just move the gap from "undocumented" to "lies at
  the API boundary."
- **`TenantContext` is a plain frozen `dataclass`, not a Pydantic
  `BaseModel`.** It's an internal DI value object read out of
  `request.state`, never a request/response body FastAPI serializes —
  using `BaseModel` for it would imply it's part of the public API
  contract, which it isn't.
- **The tenant-context stub is genuinely wired through middleware, not
  hardcoded in `deps.py`.** `TenantContextMiddleware` sets
  `request.state.org_id` from an `X-Org-Id` header (falling back to
  `PLACEHOLDER_ORG_ID`, a well-known nil UUID, chosen over `None` so a
  Phase 4+ tenant-scoped query never needs a `None`-check special case);
  `get_tenant_context` just reads it back typed. This means the seam
  where real JWT-derived identity gets plugged in later is the
  middleware's `dispatch` body, not every route's dependency signature —
  route code doesn't change when real auth arrives.
- **`/health/ready` runs a real `SELECT 1` against Postgres, breaking the
  "stub only" pattern on purpose.** `PROJECT_HANDBOOK.md`'s "not real
  logic yet" instruction is about the RAG business logic this phase
  exists to defer (retrieval, generation, tenant-scoped queries) — a
  liveness/readiness probe is standard infra plumbing, and an
  always-`"ok"` readiness endpoint would be actively misleading the
  moment this is ever deployed behind an orchestrator. `/health`
  (liveness) stays a true no-dependency stub so a slow/down Postgres
  can't get a healthy process killed by a liveness-probe restart loop —
  only `/health/ready` (readiness) checks the database and returns 503 +
  `{"status": "degraded"}` if it can't reach it.
- **Ruff's `B008` (flake8-bugbear, "no function calls in argument
  defaults") had to be explicitly relaxed for `fastapi.Depends`** via
  `[tool.ruff.lint.flake8-bugbear].extend-immutable-calls` in
  `services/api/pyproject.toml`. `Depends(...)` as a parameter default is
  FastAPI's own documented DI pattern, not the mutable-default footgun
  `B008` is designed to catch — every route in `api/v1/routes/` tripped
  it before this config change. This is a lint-config fix, not a new
  dependency; flagged here since it's a small but easy-to-miss detail for
  anyone reproducing `ruff check src` cleanly.
**Key concepts a reviewer should understand:**
- **Starlette's `add_middleware` prepends, so the last-registered
  middleware runs first.** `main.py` registers `RateLimitMiddleware`,
  then `TenantContextMiddleware`, then `AuthMiddleware` — in that call
  order — which produces `Auth -> TenantContext -> RateLimit -> route` as
  the actual request-execution order (verified by tracing
  `Starlette.build_middleware_stack`: each `add_middleware` call inserts
  at index 0 of `user_middleware`, and the stack is built by wrapping in
  reverse, so the most-recently-added middleware ends up outermost). This
  is the order that's semantically correct — resolve identity, then
  resolve which tenant that identity belongs to, then rate-limit per
  tenant — and it's the opposite of what registering them in that same
  order would intuitively suggest, which is exactly why it's worth
  understanding rather than just copying.
- **The app is built by a `create_app()` factory, not a bare
  module-level `FastAPI()`.** Cheap now, but it's what lets a later
  phase's tests construct a fresh app with `app.dependency_overrides[get_db]`
  swapped for a test session, without import-order tricks.
- **Every route already depends on `get_db` and `get_tenant_context`,
  even though no route body uses either yet.** The point of this phase
  per `PROJECT_HANDBOOK.md` is proving the API *surface*, and the DI
  wiring is part of that surface — a route that doesn't request the
  session/tenant dependency now would need its signature changed later
  just to add them, which is exactly the kind of interface churn a
  skeleton phase exists to avoid.
**Tradeoffs / deliberately left out:**
- No route enforces anything based on `tenant.role` yet (e.g. admin-only
  on `/admin/*`) — `TenantContextMiddleware` never sets a real role
  (always `None`), so there's nothing meaningful to check against until
  real auth exists. Noted inline in `admin.py` rather than adding a
  no-op authorization check that would just be decorative.
- `AuthMiddleware` doesn't reject anything — a missing or malformed
  `Authorization` header is not an error at this phase, it just means
  `request.state.auth_token` is `None`. Real verification (signature,
  expiry, 401 on failure) is later-phase work; the stub's only job is to
  establish where that logic will live.
- No integration tests for the routes yet (e.g. `tests/integration/
  test_query_endpoint.py` from `Financial_RAG_Project_Structure.md`'s
  plan) — verified manually this phase instead (`mypy`/`ruff` clean;
  `uvicorn` boot-tested against the real `docker-compose.yml` Postgres;
  every endpoint exercised via `curl`, including a 422 on an invalid
  `QueryRequest` and the `X-Org-Id` header round-tripping through
  `TenantContextMiddleware` into a response). Real integration tests
  belong once there's real logic worth regression-testing — testing that
  a stub returns its own hardcoded placeholder is low-value.
**How it connects to the rest of the system:** This is the seam every
later phase fills in without changing shape: Phase 4 replaces
`documents.py`'s bodies with real `Document` queries/writes scoped by
`tenant.org_id`; Phase 6 replaces `query.py`'s bodies with the actual
retrieval/generation pipeline and starts populating `QueryResponse`'s
`citations` for real; Phase 7 does the same for `admin.py`. None of those
phases need to touch `main.py`, the middleware stack, or any schema's
field names — only what currently returns placeholder data.

---

## [2026-08-08] Documents are shared reference data, not org-owned — the ER-model gap Phase 4 surfaced
**Phase:** 4 — Wire the Library page end-to-end
**What was built:** No code yet — this entry records a design decision
made *before* touching `documents.py`, per `CLAUDE.md` §4's "if the ER
model has a real gap, say so explicitly" rule. `PROJECT_HANDBOOK.md`'s
Phase 4 prompt says `GET /documents` should be "scoped by tenant context,"
but `docs/architecture.md` §7's ER diagram has **no relationship at all**
between `ORGANIZATION` and `COMPANY`/`DOCUMENT` — `Document` has no
`org_id`, direct or indirect. Implementing literal row-level tenant
scoping would have meant adding one, which is a real deviation from the
pasted ER diagram, not just an additive column — it changes what kind of
thing a `Document` *is* (org-private vs. shared). Flagged to Sam and
resolved via `AskUserQuestion` rather than picked silently.
**Why this approach:** Went with "shared corpus, no row filtering" over
"add `Document.org_id`." SEC filings are public documents — every
tenant's analysts asking about NVDA's 10-K are looking at the *same*
10-K, not their own private copy of it. Per-org siloing would mean two
orgs independently re-uploading and re-ingesting the identical public
filing, paying the embedding/parsing cost twice for zero isolation
benefit (there's no confidential data in a public SEC filing to protect
between tenants). `GET /documents` therefore returns every `Document`
unfiltered; `tenant` stays in both route signatures anyway (matching
every route since Phase 3) since a per-tenant *visibility* toggle over
the shared corpus — as opposed to *ownership* — is still a plausible
Phase 7 admin feature.
**Key concepts a reviewer should understand:**
- This is a distinct kind of multi-tenancy question from "does `User`
  belong to one `Organization`" (already true, Phase 2). Reference/master
  data (companies, their public filings) and tenant-private data
  (conversations, queries, citations, eval results) don't have to follow
  the same ownership model in the same schema — conflating them would
  have been the actual mistake here, not the other way around.
- If per-tenant *access control* over the shared corpus is ever needed
  (e.g. an enterprise tier that restricts which tickers an org can query),
  that's a join table (`organization_document_access` or similar), not an
  `org_id` FK on `Document` — worth remembering as the shape that decision
  should take if it comes up.
**Tradeoffs / deliberately left out:** No visibility restriction of any
kind exists yet — every org sees every document, full stop. Acceptable
now (single-tenant local dev/demo, no real orgs), explicitly a Phase 7+
concern if it ever becomes real.
**How it connects to the rest of the system:** This decision is what
makes `list_documents`/`create_document` in `documents.py` correct rather
than merely simple — see that entry below for the implementation.

---

## [2026-08-08] `Document.title` + `Document.status` columns
**Phase:** 4 — Wire the Library page end-to-end
**What was built:** Two additive columns on `Document`:
`title: Mapped[str]` (`String(512)`, not null) and
`status: Mapped[DocumentStatus]` (new Postgres enum
`PENDING | PROCESSING | COMPLETED | FAILED`, not null, defaults to
`PENDING`). Migration `8c520544e49c_add_document_title_and_status`,
chained onto the existing head.
**Why this approach:** Both were flagged gaps from earlier phases, not
new discoveries: Phase 2's `document.py` decisions-log entry explicitly
deferred `status` to "whichever phase actually needs a pending/
processing/complete document lifecycle" (that's this one), and separately
noted the ER diagram has no display-name field for a `Document` at all —
the Library page can't render a document list with neither. `DocumentStatus`
includes `PROCESSING`/`FAILED` even though Phase 4's own write path only
ever sets `PENDING` — Phase 5's real Celery task is the only thing that
will ever move a row through the other two, and the Library page's status
badge already needs to render all four distinctly (see `Library.tsx`'s
`StatusBadge`), so this is one migration doing that job instead of two
piecemeal ones later.
**Key concepts a reviewer should understand:**
- **Alembic autogenerate under-produces DDL for a new enum column added
  to an *existing* table.** `op.create_table(...)` with an inline
  `sa.Enum(...)` column implicitly emits `CREATE TYPE` as part of the
  table-creation DDL event (that's why the four Phase-2 enums "just
  worked"), but `op.add_column(...)` on a table that already exists does
  **not** trigger that same event — autogenerate's raw output tried to
  `ALTER TABLE ... ADD COLUMN status document_status ...` against a type
  that was never created, and failed with
  `psycopg2.errors.UndefinedObject: type "document_status" does not
  exist`. Caught by actually running `alembic upgrade head` against the
  real Postgres, not just eyeballing the generated file — the fix is a
  hand-added `document_status_enum.create(op.get_bind(), checkfirst=True)`
  call before the `add_column`, with the matching `.drop(...)` in
  `downgrade()`. Worth remembering for every future migration that adds
  an enum column to a table that isn't brand-new in the same migration.
- Postgres's DDL is transactional, so this failure rolled back cleanly
  with zero partial state — confirmed via `\d documents` showing neither
  column present, and `alembic_version` still at the prior head, before
  fixing and re-running. A useful thing to have actually verified once,
  not just assumed.
- `status` gets a Python-side `default=DocumentStatus.PENDING` only (no
  `server_default`) — matches the existing convention `Organization.tier`
  already set in Phase 2, not a new pattern.
**Tradeoffs / deliberately left out:** No backfill logic in the migration
for `title` (`NOT NULL`, no default) — safe here only because the
`documents` table was empty when this ran; if this schema had real rows
already, `title` would need either a `server_default` or a data-backfill
step before the `NOT NULL` could be added. Flagging so this migration
isn't copied as a template without noticing that assumption.
**How it connects to the rest of the system:** `DocumentResponse`
(schemas) and `Library.tsx`'s table/status-badge both consume these two
columns directly; `scripts/seed_dev_data.py` sets a mix of `COMPLETED`/
`PROCESSING` seed rows so the badge's two "real" states are both visible
without needing a live Celery worker.

---

## [2026-08-08] Real `GET/POST /documents` — find-or-create companies, local PDF storage, stub Celery enqueue, CORS
**Phase:** 4 — Wire the Library page end-to-end
**What was built:** `documents.py`'s stub bodies replaced with real logic.
`GET /documents` queries every `Document` (joined-loaded with `Company`),
newest upload first. `POST /documents` takes a real `multipart/form-data`
upload (`UploadFile` + individual `Form(...)` fields for
ticker/document_type/fiscal_year/fiscal_quarter/company_name/sector/title),
resolves or creates the `Company` by ticker, saves the PDF to local disk
(`src/infra/storage.py`), writes a `Document` row with `status=PENDING`,
and enqueues a Celery task (`src/infra/celery_app.py`) against a
genuinely-registered no-op `ingest_document` task. Also added
`CORSMiddleware` to `main.py` — required for `Library.tsx`'s browser
`fetch` calls to work at all (see below).
**Why this approach:**
- **Individual `Form(...)` params, not a Pydantic submodel.** First tried
  `Annotated[DocumentCreateForm, Form()]` (FastAPI's documented pattern
  for a Pydantic model as form data, available since 0.113). Live-tested
  it with `curl` before trusting it, and it failed: combined with a
  sibling `File(...)` parameter, FastAPI nests the model's fields under
  its own parameter name (`{"file": ..., "form": {...}}`, confirmed via
  `/openapi.json`'s generated schema) instead of flattening them — not
  what a plain HTML `<input type="file">` + `FormData()` actually posts.
  Switched to one `Annotated[X, Form(...)]` parameter per field (the
  classic FastAPI file-upload-plus-fields pattern), which flattens
  correctly. This is exactly the kind of thing that looks right by
  reading FastAPI's docs and is wrong in practice — worth remembering
  that this combination specifically doesn't work as documented.
- **Company resolution is find-or-create by ticker, not a required
  `company_id`.** There's no company-picker UI or `GET /companies`
  endpoint for the frontend to source a `company_id` from, and building
  one is out of Phase 4's stated scope. An unknown ticker creates a new
  `Company` (name defaults to the ticker, sector to `"Unknown"`) rather
  than 400ing and forcing a separate "register a company first" step that
  doesn't exist anywhere in this UI.
- **PDF bytes are actually persisted to local disk**
  (`<repo root>/data/uploads/<document_id><ext>`, overridable via
  `UPLOAD_DIR`), not just the metadata row. `docs/architecture.md` §1
  describes "an analyst... uploads a raw PDF," and the Phase 4 DoD says
  literally "upload a PDF through the running frontend" — a
  metadata-only endpoint wouldn't actually satisfy that, and Phase 5's
  ingestion task needs real bytes to parse. Deliberately *not* S3/blob
  storage (nothing in `CLAUDE.md` §3's agreed stack yet) — local disk
  only works because `services/api` and `services/ingestion` share a
  filesystem in local dev; flagged in `storage.py`'s docstring as a
  Phase-9-must-revisit, the same way `docs/architecture.md` §4 already
  treats Qdrant/Postgres as "managed services in production."
- **The Celery stub task lives in `services/api`, not `services/ingestion`.**
  `services/ingestion` still has zero application code — writing its real
  task now would be doing Phase 5's work inside Phase 4, one of
  `CLAUDE.md` §4's explicit stop-and-ask boundaries. The stub is
  registered under the exact task name (`"ingest_document"`) Phase 5's
  real task will reuse, so anything already sitting in the Redis queue
  from Phase 4 testing gets picked up once a real worker exists, no
  rename needed.
- **A down Celery/Redis broker doesn't fail the request.** `.delay()` is
  wrapped in a `try`/`except` that logs a warning on failure rather than
  raising — the `Document` row is already correctly committed as
  `PENDING` either way, and failing the whole write because the *async*
  side hiccupped would undermine the exact "decoupled write path"
  property `docs/architecture.md` §3 calls out as this architecture's
  reason to exist.
- **CORS was missing, and only became visible by actually driving the
  page in a real browser.** Every backend check up to this point (`curl`,
  `mypy`, `ruff`, `pytest`) passed cleanly, because none of them are
  subject to the browser's CORS policy — only an actual `fetch()` from a
  page served on a different origin (Vite's `5173` vs. the API's `8000`)
  triggers it. Caught via a full Playwright-driven run of the real
  Library page (see `Library.tsx`'s decisions-log entry) that showed
  "Failed to fetch" and a `console` CORS error, not by reasoning about it
  in advance. `CORSMiddleware` is registered last (outermost), so a
  browser's preflight `OPTIONS` request is answered before it reaches
  `Auth`/`TenantContext`/`RateLimit`, none of which have anything
  meaningful to check on a preflight anyway.
**Key concepts a reviewer should understand:**
- The find-or-create has an accepted, unguarded race (two concurrent
  uploads for a brand-new ticker could both miss the `SELECT` and one
  loses to `companies.ticker`'s unique constraint on `commit`) — fine for
  a single-analyst local-dev/demo workload, called out explicitly in the
  route's own docstring rather than silently accepted.
- `content = await file.read()` makes `create_document` `async def`
  while every other route in this file stays a plain `def` — FastAPI runs
  sync routes in a threadpool and async routes on the event loop
  regardless of which dependencies they use, so mixing the two in one
  router file is fine; this route needs `async` specifically because
  `UploadFile.read()` is a coroutine.
**Tradeoffs / deliberately left out:** No pagination on `GET /documents`
(`total` always equals `len(documents)`) — dataset stays small at this
phase, and the response envelope already has a separate `total` field so
a future paginated implementation doesn't need a shape change. No
`GET /companies` endpoint yet (see above).
**How it connects to the rest of the system:** This is what
`frontend/src/app/lib/api.ts` calls and what `scripts/seed_dev_data.py`
writes rows compatible with (same `Document`/`Company` models, same
`title`/`status` columns). Phase 5's real Celery task replaces
`ingest_document_stub`'s body under the same task name; Phase 5's
`metadata_writer.py` is what will eventually flip a row from `PENDING` to
`PROCESSING`/`COMPLETED`/`FAILED`.

---

## [2026-08-08] `scripts/seed_dev_data.py`
**Phase:** 4 — Wire the Library page end-to-end
**What was built:** A standalone script that inserts the same four
companies (NVDA/AMD/INTC/TSM) and six documents the old `MOCK_DOCS` array
in `Library.tsx` hardcoded, now as real `Company`/`Document` rows.
Idempotent by application-level check (skips a document if one already
exists for the same company/type/fiscal_year/fiscal_quarter), not a
database constraint.
**Why this approach:** Deliberately mirrors the old mock data's tickers,
titles, and dates rather than inventing new sample data — swapping
`MOCK_DOCS` for a real fetch shouldn't also change what the demo looks
like on first run. `MOCK_DOCS`'s `"Other"` type has no `DocumentType`
equivalent (the enum has exactly four values, by design — no generic
bucket, see `enums.py`'s Phase 2 entry), mapped to `INVESTOR_DECK` as the
closest fit rather than adding a fifth enum value outside the agreed
stack for one seed row.
**Key concepts a reviewer should understand:**
- Idempotency is script-level, not schema-level — there's no
  `UniqueConstraint` on `(company_id, document_type, fiscal_year,
  fiscal_quarter)` in the actual `documents` table (nothing asked for one,
  and a real analyst genuinely might upload two distinct documents that
  happen to share all four of those values), so this only protects
  against *this script* being re-run, not general duplicate inserts from
  elsewhere. Verified by actually running it twice — first run reported
  6 created/0 skipped, second reported 0 created/6 skipped.
- These rows are metadata-only: `source_url` is a fake
  `seed-data/<ticker>-<year>...pdf` path with no real file behind it,
  unlike a document created through the real upload flow. Documented
  in the script's own docstring so nobody's confused later about why
  opening one of these doesn't work.
**Tradeoffs / deliberately left out:** Run manually (`python
scripts\seed_dev_data.py`), not wired into any migration or app startup
hook — seed data staying a deliberate, explicit action rather than
something that silently happens is the right default until there's a
reason (e.g. CI fixtures) to automate it.
**How it connects to the rest of the system:** Imports `SessionLocal` and
the `Document`/`Company`/enum models directly from `services/api/src`
(path-inserted at the top of the script, since `scripts/` sits outside
`services/api`) — the same models `documents.py`'s routes use, so a
seeded row and a really-uploaded row are indistinguishable to the API or
the frontend.

---

## [2026-08-08] `Library.tsx` wired to real data — API client, upload dialog
**Phase:** 4 — Wire the Library page end-to-end
**What was built:** `MOCK_DOCS` removed entirely. `Library.tsx` now
fetches real documents on mount (loading/error/retry states), and a new
upload dialog (file picker + ticker/document-type/fiscal-year/quarter/
title fields, plus a collapsed "company details" section for a new
ticker) posts a real `multipart/form-data` request and prepends the
created row on success. A new `frontend/src/app/lib/api.ts` holds the
shared fetch client (base URL, TS types mirroring the Pydantic schemas,
error-message parsing) and `frontend/.env.example` documents
`VITE_API_BASE_URL`.
**Why this approach:**
- **Upload dialog is a hand-rolled fixed-overlay `div`, not the shadcn
  `Dialog` primitive already sitting in `components/ui/dialog.tsx`.**
  Checked first: `Dialog`'s `DialogContent` uses `bg-background`/
  `text-muted-foreground` (shadcn's CSS-variable theme tokens), but
  `docs/progress.md`'s Known Issues already flags those tokens as
  disconnected from this app's actual dark palette, and nothing else in
  the app currently uses this Dialog component. `Layout.tsx`'s existing
  "New Project" modal is a hand-rolled `fixed inset-0` overlay styled
  with literal `zinc-800`/`#0f0f11` classes — matched that pattern
  exactly (same overlay/backdrop/rounded-card structure, same
  uncontrolled-form-plus-`FormData` idiom for reading the submission)
  instead of introducing a second, visually-inconsistent modal
  convention into the same codebase.
- **`lib/api.ts` is a new (small, obvious) folder, not inline fetch
  calls in `Library.tsx`.** Phase 6/7 wire `Chat.tsx`/`Compare.tsx`/
  `Admin.tsx` to this same API next and will want the same base-URL and
  error-parsing logic — worth the one extra file now rather than
  duplicating `fetch` boilerplate three more times shortly.
- **Client-side filtering (`searchTerm`) is unchanged in spirit from the
  original mock:** the original `MOCK_DOCS.filter(...)` was never scoped
  by `activeProject` either (that's a purely client-local concept with no
  backend equivalent — see the ER-model-gap entry above), so real
  documents aren't project-filtered here either. Preserves existing
  behavior with real data rather than inventing new scoping semantics
  nobody asked for.
- **Status badge gained a fourth (`failed`) visual state** the original
  two-state mock never needed (`Indexed`/`Processing` only) — `Document`
  now has a real `FAILED` status Phase 5's ingestion task can reach, and
  silently collapsing it into the `Processing` badge would hide a
  genuinely different, actionable state from an analyst.
**Key concepts a reviewer should understand:**
- **CORS was the actual blocker, not React code** — `npm run build`
  passed, `mypy`/`ruff`/`pytest` all passed, and the page still failed
  entirely on first real-browser test (`Failed to fetch`, confirmed via a
  headless Playwright run against the actual dev server, not just code
  review). Fixed in `main.py` (see the routes entry above). This is the
  reason this phase's verification included an actual Playwright-driven
  browser pass — none of the faster checks would have caught a
  browser-only, cross-origin-only failure mode.
- Uncontrolled `<input name="...">` fields read via `new FormData(e.target)`
  on submit, matching `Layout.tsx`'s existing form idiom — no per-field
  `useState`, so the file input in particular (which can't be a
  controlled React input at all) doesn't need special-casing next to the
  text/number fields.
**Tradeoffs / deliberately left out:** No client-side PDF validation
beyond the native `accept="application/pdf"` file-picker hint — the
server-side `Content-Type` check is the real guard (already covers the
happy path; a user renaming a `.txt` to `.pdf` would still 400 server-side,
which is enough at this phase). No drag-and-drop upload — out of scope
for a first wiring pass. `Download`/`MoreHorizontal` row actions remain
inert placeholders (unchanged from the mock) since there's no
`GET /documents/{id}/file` endpoint yet.
**How it connects to the rest of the system:** Calls
`services/api/src/api/v1/routes/documents.py` directly; the TS types in
`lib/api.ts` are a hand-kept mirror of `models/schemas/document.py`'s
Pydantic schemas (no shared codegen between the two — flagged as a
known drift risk if the two are ever edited independently).

---

## [2026-08-09] Frontend's API base URL default moved from port 8000 to 8001 (setup)
**Phase:** setup fix — not one of the nine build phases, no
`docs/progress.md` phase rows updated for this entry (per Sam's explicit
instruction — this doesn't change what's built, only where the frontend
looks for it on this machine).
**What was built:** `frontend/src/app/lib/api.ts`'s `API_BASE_URL`
fallback and `frontend/.env.example`'s documented `VITE_API_BASE_URL`
default both changed from `http://localhost:8000/api/v1` to
`http://localhost:8001/api/v1`. Nothing else — the path
(`/api/v1/documents` etc.) was already correct; only the port was wrong.
**Why this approach:** Confirmed via a full `grep` of `frontend/src` for
`8000`/`localhost` that exactly one place in source hardcoded the port
(`lib/api.ts`'s fallback constant — the same file Phase 4 built as the
single shared fetch client specifically so a change like this only has
one call site to fix). No `frontend/.env`/`frontend/.env.local` exists on
this machine yet (only the checked-in `.env.example` template), so there
was no actual runtime override masking or duplicating this value —
confirmed by listing `frontend/`'s dotfiles before editing, not assumed.
Port 8000 is permanently occupied on this dev machine by an unrelated
local project's Docker container (`veritasrag-api`) — already noted as a
pre-existing collision in `docs/progress.md`'s Phase 3 "Known Issues"
(`com.docker.backend.exe`/`wslrelay.exe` observed listening on host port
8000), which flagged it as a reason `localhost:8000` isn't a *unique*
signal this API is running, but didn't act on it since nothing was
calling the API cross-origin yet at that point — this is the same class
of local port collision `docker-compose.yml`'s Qdrant remap (6333→6335,
6334→6336) already handles for the same reason, just surfacing on the
API's own port instead of Qdrant's this time.
**Key concepts a reviewer should understand:**
- This is a **machine-local dev port**, not a canonical project default —
  `uvicorn`'s own default (8000) and `PROJECT_HANDBOOK.md`'s cheat sheet
  (`uvicorn src.main:app --reload`, no `--port` flag) are both left
  as-is. Anyone without this specific machine's port collision runs the
  API on 8000 as documented and only needs `VITE_API_BASE_URL` (or this
  fallback) if they deviate from that. `frontend/.env.example` now says
  so explicitly and documents the actual run command
  (`--port 8001`) needed to match its new default.
- Same reason `API_BASE_URL` was built as a single `??`-fallback constant
  in Phase 4 rather than inlined per call site: a port change like this
  is a one-line diff instead of a grep-and-replace across every page that
  calls the API.
**Tradeoffs / deliberately left out:** Didn't touch
`CORS_ALLOWED_ORIGINS` in `services/api/src/main.py` — that allowlist is
about which *frontend* origin may call the API (Vite's port, 5173),
which didn't change; it's unrelated to which port the API itself listens
on. Didn't touch `PROJECT_HANDBOOK.md`'s command cheat sheet or any other
doc mentioning port 8000 — those describe the canonical/default setup,
not this machine's local workaround, and changing them would misrepresent
the project's actual default to anyone else following the handbook.
**How it connects to the rest of the system:** Purely a frontend-side
fix; `services/api` itself needs to actually be started with
`--port 8001` on this machine for `Library.tsx`'s fetch calls to reach it
(and every future page Phase 6/7 wires up through the same
`lib/api.ts` client inherits this fix automatically, with no further
per-page changes).

---

## [2026-08-09] Provider decisions: Cohere for embeddings, OpenAI for agentic chunking
**Phase:** 5 — ingestion pipeline (setup)
**What was built:** No code — a recorded decision, asked of Sam directly
before writing `embedder.py` or `agentic_chunker.py`, since both are new
external dependencies `CLAUDE.md` §4 requires stopping for.
**Why this approach:** `.env.example`/the Phase 2 decisions-log entry both
already flagged the embedding provider as explicitly undecided
(`EMBEDDING_API_KEY` was a deliberate placeholder name), and no LLM vendor
for "LLM-assisted" chunking was named anywhere in the docs at all — two
genuine gaps, not two places to quietly pick a default. Asked as a single
two-part question:
- **Embeddings -> Cohere** (`embed-english-v3.0`, 1024-dim), not OpenAI or
  local HuggingFace. Reuses the vendor/key/`cohere` dependency already
  agreed for `services/api`'s reranker (`CLAUDE.md` §3) — one API
  relationship covers both, instead of adding a second vendor on top of
  Cohere for embeddings alone.
- **Agentic chunking LLM -> OpenAI** chat completions (`gpt-4o-mini` by
  default), not Anthropic or a heuristic-only placeholder. This is a
  genuinely new vendor (`openai` added to `services/ingestion/
  requirements.txt`, `OPENAI_API_KEY` added to `.env.example`) — accepted
  as the cost of actually building the "LLM-assisted" chunking step
  `PROJECT_HANDBOOK.md` names explicitly, rather than deferring it.
**Key concepts a reviewer should understand:**
- This is `CLAUDE.md` §4's stop-and-ask boundary working as intended: two
  real architectural choices existed, neither was defensible to make
  silently, and both were resolved by asking rather than by picking
  "whatever's easiest to code."
- The OpenAI dependency is *optional at runtime*, not just in principle:
  `agentic_chunker.py` checks for `OPENAI_API_KEY` and falls back to a
  deterministic heuristic splitter if it's absent or the call fails --
  see that file's own decisions-log entry. Ingestion works end-to-end
  with zero `OPENAI_API_KEY` set, confirmed by this phase's live smoke
  test (real Postgres/Qdrant/Cohere, no OpenAI key in `.env`).
**Tradeoffs / deliberately left out:** Two LLM vendors now exist in the
stack (Cohere for rerank+embeddings, OpenAI for chunking) rather than
one -- accepted because Cohere doesn't offer a general chat-completion
API suited to structured JSON boundary detection the way its embed/rerank
endpoints are purpose-built for search. Phase 6's `answer_generator.py`
will need its own LLM-provider decision; this entry doesn't presume that
one has to be OpenAI too, though reusing OpenAI would avoid a third
vendor.
**How it connects to the rest of the system:** Every other Phase 5 entry
below that touches `embedder.py` or `agentic_chunker.py` assumes this
decision without re-litigating it.

---

## [2026-08-09] Shared SourceLocation type (packages/shared)
**Phase:** 5 — ingestion pipeline
**What was built:** `packages/shared/aegis_shared/` -- a small, editable-
installed Python package (`pip install -e ../../packages/shared`, wired
into `services/ingestion/requirements.txt`) holding one dependency-free
frozen dataclass, `SourceLocation` (`document_id`, `page_number`,
`chunk_type`, `chunk_index`, `table_cell_ref`), with `exact_location()`,
`to_qdrant_payload()`, and `from_qdrant_payload()`.
**Why this approach:** `docs/architecture.md` §2 names the `source_location`
concept -- "built once, at ingestion time, and travels unchanged ... into
the final citation object" -- as the single most important design
decision in the ingestion pipeline. Putting the *type* itself in
`packages/shared` (named for exactly this purpose in `PROJECT_HANDBOOK.md`
§4's repo structure map, unused until now) turns "unchanged" from a
convention two independently-maintained copies have to keep agreeing on
by hand into a fact about the code: `services/ingestion` constructs one
instance per chunk today; Phase 6's `citation_resolver.py`
(`services/api`) will import this exact class to read one back out of a
retrieved Qdrant point.
Packaged as a real installable local package (`pyproject.toml`,
`setuptools` backend, `pip install -e`), not a copy-pasted file or a
`sys.path` hack -- the standard, correct answer for genuinely shared code
in a multi-service repo. `setuptools` over `hatchling` for the build
backend: one fewer new build-tool dependency to fetch, no functional
difference at this size.
**Key concepts a reviewer should understand:**
- Deliberately dependency-free (no SQLAlchemy, no service imports) --
  this is the one thing to get right here, since anything heavier would
  mean importing this package drags in whichever service's stack that
  dependency belongs to.
- `mypy` couldn't resolve the editable install by default -- modern
  `setuptools` editable installs use an import-hook `MetaPathFinder`
  (`__editable___aegis_shared_..._finder.py` in site-packages) that the
  real Python interpreter follows at runtime but `mypy`'s static import
  resolution doesn't. Fixed with `mypy_path = ["../../packages/shared"]`
  in `services/ingestion/pyproject.toml`, pointing mypy at the real
  source directly rather than through the install mechanism -- confirmed
  necessary by reproducing the `import-not-found` error first, not
  assumed.
- A `py.typed` marker was added to `aegis_shared` on the same reasoning
  as `docs/DECISIONS_LOG.md`'s existing celery-stub-gap entries: a
  shared, typed library should declare itself typed so consumers' `mypy`
  runs trust its signatures instead of treating it as untyped.
**Tradeoffs / deliberately left out:** `services/api` does not yet
install this package -- nothing there needs it until Phase 6's
`citation_resolver.py`. Explicitly flagged in `docs/progress.md`'s
"Immediate Next Step" so it isn't a surprise. Exact character-offset
spans aren't tracked (`text_span` is chunk-ordinal, e.g. `"chunk 2"`, not
a `(start, end)` pair) -- narrower than a citation system could ideally
want, accepted for now since `agentic_chunker.py` doesn't track character
offsets against the *original page text* either (its boundaries are
relative to already-extracted narrative text, and the source PDF's exact
text-layer offsets aren't preserved past `pdf_parser.py`).
**How it connects to the rest of the system:** Constructed in
`services/ingestion/src/tasks/ingest_document.py`, consumed by
`src/storage/qdrant_writer.py` (`to_qdrant_payload()`). Nothing reads
`from_qdrant_payload()` yet -- included now so Phase 6 has a symmetric
read path already defined rather than guessed at later.

---

## [2026-08-09] services/ingestion's own mirrored ORM models + infra layer
**Phase:** 5 — ingestion pipeline
**What was built:** `services/ingestion/src/storage/models.py` (a second,
independent set of SQLAlchemy 2.0 models -- `Company`, `Document`,
`DocumentChunk`, `TableData`, plus mirrored `DocumentStatus`/`ChunkType`
enums) and the ingestion-side infra layer: `src/infra/db.py` (engine/
session, same shape as `services/api`'s), `src/infra/celery_app.py` (the
consumer-side Celery app, `include=["src.tasks.ingest_document"]`), and
`src/infra/storage.py` (`resolve_source_path`, the read-side counterpart
to the API's `save_uploaded_pdf`).
**Why this approach:** The one real architectural fork in this phase.
`services/api/src/models/db/` already has full, working `Document`/
`DocumentChunk`/`TableData` models -- the obvious-looking alternative was
importing those directly from `services/ingestion`. Rejected, for three
reasons: (1) `PROJECT_HANDBOOK.md` §6 Phase 5's file list is scoped
entirely to `services/ingestion/src/`, not a refactor of already-migrated,
already-tested Phase 2-4 files; (2) `services/api/src/infra/
celery_app.py`'s own Phase 4 docstring already established the governing
principle for this exact service pair -- "the two ... instances only ever
agree by convention ..., never by sharing Python code" -- written for the
Celery app but equally true for the ORM layer, since `docs/architecture.md`
§3 calls the services "deliberately decoupled" specifically so they can
scale independently, and a cross-service Python import would silently
undo that (you could no longer ship an ingestion worker without the API's
source tree present); (3) the actual point of agreement between the two
model sets is the Postgres schema itself (table/column/enum-type names,
created once by the API's Alembic migrations) -- not Python class
identity.
**Key concepts a reviewer should understand:**
- Only the columns each writer/reader actually touches are declared here
  -- no `relationship()`s, since this file only ever does Core-style
  `select`/`insert ... on_conflict_do_update`/`update`, never ORM graph
  navigation.
- `PgEnum(DocumentStatus, name="document_status", create_type=False)` --
  `create_type=False` stops SQLAlchemy from ever trying to `CREATE TYPE`
  (the enum already exists from the API's migration); moot today since
  nothing here calls `Base.metadata.create_all()`, but explicit rather
  than relying on that never happening by accident.
- `document_type` is mapped as a plain `String`, not a third enum
  duplicate -- ingestion only ever *reads* this column (for
  `document_classifier.py`'s mismatch check and Qdrant payload metadata),
  never writes it, so a plain string read is simpler than mirroring an
  enum this file has no reason to validate against.
**Tradeoffs / deliberately left out:** Real coordination cost accepted:
if the API's Alembic migrations ever rename/retype one of these columns,
both model files need updating in lockstep, and nothing enforces that
automatically. Judged cheaper than the cross-service import coupling it
avoids, and consistent with a precedent this repo already set (the two
`celery_app.py` files agreeing only by broker URL + task name).
**How it connects to the rest of the system:** `src/storage/
metadata_writer.py` is the only consumer of `models.py`. `src/infra/
storage.py::resolve_source_path` is the first thing `tasks/
ingest_document.py` calls after loading a `Document` row, turning its
`source_url` into an openable path for `src/parsing/pdf_parser.py`.

---

## [2026-08-09] pdf_parser.py — pymupdf structural parse
**Phase:** 5 — ingestion pipeline
**What was built:** `services/ingestion/src/parsing/pdf_parser.py`'s
`parse_pdf()`, returning a `ParsedDocument` of `ParsedPage`s, each with
plain text, font-annotated `TextLine`s (size + bold, per span), and
candidate table bounding boxes from pymupdf's own `Page.find_tables()`.
**Why this approach:** Every downstream parsing/chunking stage consumes
this module's output rather than touching `pymupdf` directly, so there's
exactly one place in the codebase that knows how to walk a
`pymupdf.Document`. Table-bbox detection lives here rather than in
`layout_segmenter.py` (which conceptually "owns" the narrative/table/
footnote split) because it needs the live `pymupdf.Page` object this
module already has in scope while iterating -- `layout_segmenter.py`'s
job is the classification logic that *consumes* these bboxes, not
re-deriving pymupdf primitives a second time.
**Key concepts a reviewer should understand:**
- Font "flags" is a bitmask (bit 4 = bold) -- pymupdf's own documented
  span format, not something invented here.
- `find_tables()` is wrapped in a broad `try/except`: it's a heuristic
  detector known to raise on some malformed content streams, and a
  detection failure should degrade to "no table candidates on this page"
  (narrative text still extracts normally), not abort the whole document
  -- consistent with `docs/architecture.md` §3's failure-path philosophy
  of degrading gracefully rather than hard-failing on a non-fatal step.
- Imports `pymupdf`, not the deprecated `fitz` alias -- confirmed via the
  installed version's own deprecation warning before writing any code
  against it.
**Tradeoffs / deliberately left out:** `find_tables()` is only a fast
*candidate* detector, not the final table extraction -- confirmed
correct in this phase's live smoke test (it flagged exactly the one page
with a real ruled table in the synthetic test PDF, no false positives on
the two text-only pages). The authoritative structured extraction is
camelot (`table_extractor.py`), deliberately slower and run only against
these candidate pages.
**How it connects to the rest of the system:** Called first, inside
`tasks/ingest_document.py`, before classification, segmentation, or table
extraction -- every other parsing-stage module takes a `ParsedDocument`
(or a page from one) as input.

---

## [2026-08-09] document_classifier.py — heuristic filing/transcript/deck classification
**Phase:** 5 — ingestion pipeline
**What was built:** `services/ingestion/src/parsing/document_classifier.py`.
`classify_document()` scores a `ParsedDocument`'s first 5 pages against
regex/keyword signal sets for `FILING`/`TRANSCRIPT`/`DECK` (plus a
sparse-text-per-page signal for decks), returning the highest-scoring
`DocumentKind` and a normalized confidence; `UNKNOWN` when no signal
fires at all. `matches_declared_type()` maps a `DocumentKind` back to the
`Document.document_type` string(s) it should agree with, used by
`tasks/ingest_document.py` to log (not enforce) a mismatch against what
the analyst picked at upload time.
**Why this approach:** Pure heuristics, no LLM -- unlike
`agentic_chunker.py`, nothing in `PROJECT_HANDBOOK.md`'s Phase 5 prompt
calls this stage "LLM-assisted," and a three-way document-shape
classification (a filing has "PART I"/"Item 7."-style section markers, a
transcript has "Operator:"/speaker-line patterns, a deck is sparse and
says "forward-looking statements") is squarely the kind of thing
regex/keyword scoring handles reliably and for free, matching
`docs/architecture.md` §1 step 2's "classify document type" without
adding a third LLM call to the pipeline.
Deliberately independent of the API's `DocumentType` enum (no import) --
`matches_declared_type` compares against plain string values instead, for
the same decoupling reason `src/storage/models.py` gives for not
importing the API's ORM models.
**Key concepts a reviewer should understand:**
- Confidence is `winning_score / total_score` across all three kinds --
  a cheap, honest signal-strength measure, not a calibrated probability.
- The deck "sparse text" bonus is guarded on non-empty sample text (`if
  sample_text.strip() and words_per_page < threshold`) -- caught by this
  phase's own unit tests: an *empty* document also has 0 words/page, but
  that's absence of evidence, not evidence of a sparse slide deck, and
  should fall through to `UNKNOWN`, not get misclassified as `DECK`.
- Live smoke-tested against two real documents: a synthetic 10-K-style
  PDF (correctly classified `FILING`, confidence 0.83) and an unrelated
  real PDF already sitting in `data/uploads/` from Phase 4 testing (a
  health-NLP paper, correctly landing on `UNKNOWN` rather than being
  forced into one of the three real kinds).
**Tradeoffs / deliberately left out:** A mismatch between the classified
kind and the analyst's declared `document_type` is only logged
(`tasks/ingest_document.py`), never blocks ingestion or overrides the
analyst's choice -- `docs/architecture.md` §3's decision table describes
a "manual-review queue" for repeated classification failures, which
doesn't exist yet as infrastructure; a warning log line is the honest
current substitute, flagged here rather than silently claimed as done.
**How it connects to the rest of the system:** Runs once per document in
`tasks/ingest_document.py`, right after `parse_pdf()`; its result is
logged for observability but doesn't currently branch any downstream
parsing behavior (segmentation/extraction run the same way regardless of
classified kind).

---

## [2026-08-09] layout_segmenter.py — narrative/table/footnote split
**Phase:** 5 — ingestion pipeline
**What was built:** `services/ingestion/src/parsing/layout_segmenter.py`.
`segment_page()` walks a `ParsedPage`'s font-annotated lines and buckets
each into narrative text, footnote text, or "belongs to a table" (dropped
from both, left for `table_extractor.py`), using per-page-median body
font size, a bottom-quartile position check, and a leading footnote-marker
regex (`"(1)"`, `"*"`, `"1."`).
**Why this approach:** This is `docs/architecture.md` §1 step 3, called
out there as "the step that matters most for accuracy" -- a table's text
leaking into a narrative chunk (or vice versa) is exactly the kind of
silent corruption that later causes a wrong number to look plausible.
Font size is computed *per page*, not as a fixed point size, since body
text size varies across filings/decks/transcripts; a marker-prefixed line
is treated as a footnote regardless of position/size, since SEC filings
sometimes place a footnote-marked line above the bottom-quartile cutoff
this heuristic would otherwise require.
**Key concepts a reviewer should understand:**
- Table-region exclusion is a genuine bbox-overlap check
  (`_overlaps`) against `pdf_parser.py`'s `find_tables()` output, not a
  page-level "is this a table page, skip everything" flag -- a table page
  can (and did, in this phase's synthetic test PDF) still have narrative
  text above the table that correctly survives into `narrative_text`.
- Confirmed against a live example, not just unit tests: this phase's
  synthetic test PDF's page 3 has both an MD&A intro sentence and a ruled
  table; the segmenter kept the sentence in `narrative_text` and excluded
  every table cell's text from both `narrative_text` and `footnote_text`.
**Tradeoffs / deliberately left out:** Footnote detection is a two-signal
heuristic (small+bottom, or marker-prefixed) with no ground truth to
tune thresholds against yet -- `_FOOTNOTE_SIZE_RATIO`/`_FOOTNOTE_Y_RATIO`
are reasonable defaults, not values validated against a labeled dataset.
Worth revisiting once Phase 8's eval harness exists and could measure
whether footnote/narrative misclassification actually affects retrieval
precision.
**How it connects to the rest of the system:** Consumes `pdf_parser.py`'s
output; produces `PageSegments`/`DocumentSegments`, which
`table_extractor.py` (via `table_page_numbers`), `agentic_chunker.py`
(narrative + footnote text per page), and `tasks/ingest_document.py` all
read from directly.

---

## [2026-08-09] table_extractor.py — camelot structured extraction with lattice/stream fallback
**Phase:** 5 — ingestion pipeline
**What was built:** `services/ingestion/src/parsing/table_extractor.py`.
`extract_tables()` runs camelot's `flavor="lattice"` parser against only
the pages `layout_segmenter.py` flagged as table candidates; any table
scoring below `_MIN_ACCURACY` (camelot's own 0-100 `parsing_report`
score) is dropped and that page retried with `flavor="stream"` instead.
Returns `ExtractedTable`s with `headers`/`rows` as separate lists.
**Why this approach:** Direct implementation of `docs/architecture.md`
§1 step 4 -- "never flatten a table into prose." Scoping camelot to
candidate pages only (not the whole document) is a deliberate cost
control: camelot re-renders/re-parses the PDF itself and is markedly
slower than pymupdf's own `find_tables()` pre-filter. Lattice-first
because SEC filings' financial tables are typically ruled; stream as a
targeted retry (only for pages where lattice scored low), not a second
full pass over every candidate page, since stream is the more
expensive/less precise parser for tables that *do* have ruling.
**Key concepts a reviewer should understand:**
- `table.accuracy < _MIN_ACCURACY`, not an exception, is the fallback
  trigger -- lattice silently produces low-confidence garbage on
  borderless tables rather than raising, so accuracy score is the only
  reliable signal that a retry is warranted.
- `table.order` (camelot's own 1-based per-page rank) becomes
  `table_index` (0-based) directly -- no separate per-page counter
  invented here, reusing what camelot already computes.
- Verified with the installed `camelot-py` 2.0 (a newer rewrite, not the
  legacy 0.x/1.x API `PROJECT_HANDBOOK.md`'s `camelot-py[cv]>=0.11` pin
  predates) via direct introspection of `camelot.io.read_pdf` and
  `camelot.core.Table` before writing any code against it, and live
  smoke-tested: correctly extracted a 4-row x 5-column ruled table from
  this phase's synthetic test PDF with headers and every cell value
  matching exactly.
**Tradeoffs / deliberately left out:** No `flavor="ml"` (Table
Transformer-based structure recognition, mentioned in `camelot-py` 2.0's
own docs) -- requires an optional heavier ML dependency
(`camelot-py[ml]`) not evaluated for this project; lattice/stream cover
the common ruled/borderless cases financial filings mostly use.
**How it connects to the rest of the system:** Called once per document
in `tasks/ingest_document.py`, after `layout_segmenter.py`; its output
feeds directly into `table_chunker.py`.

---

## [2026-08-09] agentic_chunker.py — LLM-assisted section boundaries with heuristic fallback
**Phase:** 5 — ingestion pipeline
**What was built:** `services/ingestion/src/chunking/agentic_chunker.py`.
`chunk_narrative_page()` asks OpenAI (`gpt-4o-mini`, JSON-mode, one call
per page under ~6000 chars) to identify logical section boundaries in a
page's narrative text; falls back to a deterministic paragraph-boundary
splitter (`_heuristic_section_boundaries`) if no `OPENAI_API_KEY` is set,
the call fails, or the response is malformed/overlapping. Both paths run
through `_enforce_size_bounds`, which merges undersized pieces forward
(`_merge_small_boundaries`) and hard-splits oversized ones on whitespace,
so every chunk downstream gets the same size guarantee regardless of
which path produced it. `build_footnote_chunks()` (no LLM) turns a
page's footnote text into one chunk.
**Why this approach:** This is `docs/architecture.md` §1 step 5, and the
one stage the handbook explicitly names "LLM-assisted." The fallback is a
deliberate deviation from treating every external-service failure the
same way: `docs/architecture.md` §3's failure-path table doesn't cover
this stage specifically (only embedding and rerank), and section
boundaries are a *quality* concern, not a *correctness* one the way a
wrong number is -- a paragraph-boundary-chunked document is still fully
retrievable and citable, just with less semantically clean edges. Failing
the whole ingestion job over that would be a worse tradeoff than
degrading gracefully, and this phase's live smoke test ran the entire
pipeline through the heuristic path exclusively (no `OPENAI_API_KEY` set
in `.env`) with zero ingestion failures.
**Key concepts a reviewer should understand:**
- `_merge_small_boundaries` is a forward-accumulating pass (accumulate
  into `pending` until it reaches `_MIN_CHARS_PER_CHUNK`, then flush), not
  a simple "merge into the previous entry" -- a naive backward-merge
  fails on a small *leading* boundary (nothing earlier to merge into
  yet); this was caught by this phase's own unit tests
  (`test_enforce_size_bounds_merges_slivers`), not assumed correct.
- The whitespace-split boundary is `whitespace + 1` (keeping the space as
  the trailing character of the earlier piece), not the space's own
  index -- otherwise every split-off chunk after the first would start
  with a leading space. Also caught by a failing unit test before being
  fixed.
- LLM section boundaries are validated strictly (`start < cursor`, `end
  <= start`, `end > len(text)` all rejected) before being trusted --
  a malformed or overlapping response falls back to the heuristic path
  rather than being used as-is.
**Tradeoffs / deliberately left out:** No character-offset tracking back
to the original PDF page (see `packages/shared`'s `SourceLocation` entry
for the downstream consequence). A page whose narrative text exceeds
~6000 chars skips the LLM call entirely rather than truncating/chunking
the LLM input itself -- simpler, and avoids an LLM call reasoning about
a boundary near an arbitrary truncation point.
**How it connects to the rest of the system:** Called once per page in
`tasks/ingest_document.py`'s chunk-building loop; `chunk_index` is *not*
assigned here (see that file's docstring for why it's the orchestrator's
job, not each chunker's).

---

## [2026-08-09] table_chunker.py — row-aligned table chunking
**Phase:** 5 — ingestion pipeline
**What was built:** `services/ingestion/src/chunking/table_chunker.py`.
`chunk_table()` returns one `TableChunkDraft` per `ExtractedTable` in the
common case; tables over `_MAX_ROWS_PER_CHUNK` (60) rows split into
consecutive whole-row groups, header repeated in each. `_embedding_text()`
renders a compact headers+sample-rows string used *only* as Cohere's
embedding input.
**Why this approach:** "Never split mid-row" is easy to satisfy trivially
if no test table is ever large enough to force a split -- this phase's
`tests/unit/test_table_chunker.py` specifically builds a 127-row table
and asserts the reassembled rows match the original exactly and every
split boundary falls between rows, not inside one, so the guarantee is
verified, not just asserted in a docstring.
**Key concepts a reviewer should understand:**
- `_embedding_text()`'s flattened rendering does **not** violate "never
  flatten a table" (`docs/architecture.md` §1 step 4) -- that requirement
  governs the *stored* representation (`TableData.raw_table_json` /
  Qdrant's structured payload fields), not a disposable string generated
  purely because Cohere's embed API needs *some* text input and can't
  embed JSON meaningfully. Verified live: this phase's smoke-tested table
  chunk stored the full structured `{"headers": [...], "rows": [...]}}`
  in Postgres exactly as authored, while its embedding input was the
  separate flattened summary.
- Split parts of one large table keep the same `table_index` (they're
  fragments of one logical table, not distinct tables) -- what keeps
  their `DocumentChunk` rows distinct is `chunk_index`, assigned by the
  orchestrator, not `table_index`.
**Tradeoffs / deliberately left out:** `_embedding_text` only samples the
first 5 rows for large tables' embedding input -- a semantic search
matching against row 40 of a 100-row table would rely on the header/
early-row context rather than that row's own text. Acceptable for now
since the full data is always retrievable via `raw_table_json` once the
chunk is found by any means (including a narrative reference nearby);
revisit if Phase 8's eval surfaces this as a real recall gap.
**How it connects to the rest of the system:** Called once per document
in `tasks/ingest_document.py`, after `table_extractor.py`; its
`TableChunkDraft`s feed both `embedder.py` (via `.content`) and
`metadata_writer.py`/`qdrant_writer.py` (via `.raw_table_json`).

---

## [2026-08-09] embedder.py — Cohere embeddings for narrative and table chunks
**Phase:** 5 — ingestion pipeline
**What was built:** `services/ingestion/src/embedding/embedder.py`.
`embed_texts()` batches (96 at a time) through Cohere's `ClientV2.embed`
(`embed-english-v3.0`, `embedding_types=["float"]`), preserving input
order, with `input_type` required (`"search_document"` at ingestion time;
`"search_query"` reserved for Phase 6's query-time embed call).
**Why this approach:** See the earlier "Provider decisions" entry for why
Cohere over OpenAI/local HuggingFace. Batches of 96 respect Cohere's
embed-v3 per-call text limit without the caller (`tasks/ingest_document.py`)
needing to know that limit exists. Raises on API failure rather than
degrading, unlike `agentic_chunker.py`'s LLM call -- there is no
meaningful fallback for a missing embedding (a chunk written to Postgres
without a matching Qdrant vector is permanently unretrievable), matching
`docs/architecture.md` §3's "if the provider is down, fail the ingestion
job cleanly (don't partially embed)" failure path exactly.
**Key concepts a reviewer should understand:**
- `input_type` is not cosmetic -- Cohere's v3 embed models are trained
  with different instruction prefixes per `input_type`, and using the
  wrong one measurably hurts retrieval quality. Verified the exact
  response shape (`response.embeddings.float_`) by reading the installed
  `cohere` 7.x SDK's generated types directly rather than assuming the
  v5-era API shape `PROJECT_HANDBOOK.md`'s `cohere>=5.5` pin predates.
- `EMBEDDING_DIMENSION = 1024` is a fixed constant matching
  `embed-english-v3.0`'s known output size, not derived at runtime from
  a live API call -- `qdrant_writer.py`'s `ensure_collection()` uses it
  as the default `vector_size` when creating the collection.
**Tradeoffs / deliberately left out:** No retry/backoff wrapper around
the Cohere call itself (unlike the Celery task's own
`autoretry_for`/`retry_backoff`, which covers this at the task level --
an embedding failure here propagates up and the whole task retries, not
just the embed step). Simpler, and the live smoke test's real Cohere
calls (62 texts across two real documents processed this phase) never
exercised a transient-failure path to validate a finer-grained retry
would even help.
**How it connects to the rest of the system:** Called once per document
in `tasks/ingest_document.py`, in a single batched pass over every
chunk's draft content, before any Qdrant/Postgres writes begin.

---

## [2026-08-09] qdrant_writer.py + metadata_writer.py — the two storage writes
**Phase:** 5 — ingestion pipeline
**What was built:** `services/ingestion/src/storage/qdrant_writer.py`
(`ensure_collection()`, `upsert_chunk_vector()`) and `src/storage/
metadata_writer.py` (`load_document_context()`, `set_document_status()`,
`upsert_document_chunk()`, `upsert_table_data()`,
`set_embedding_vector_id()`) -- the vector-DB and relational-DB halves of
`docs/architecture.md` §1 step 7.
**Why this approach:** Idempotency (`docs/architecture.md` §2:
"re-running ingestion on the same document should overwrite, not
duplicate") is implemented as real `INSERT ... ON CONFLICT DO UPDATE`
statements on `document_chunks` (document_id, page_number, chunk_index)
and `table_data` (chunk_id) -- not an application-level "check then
insert" (which has a race) or a "delete all chunks for this document,
then reinsert" (which would generate new `chunk_id`s every re-run,
breaking Qdrant point-ID continuity and any citation already pointing at
the old ID). `document_chunks.chunk_id` is deliberately left out of every
UPDATE's `SET` clause so a re-ingested chunk keeps its original identity.
`qdrant_writer.upsert_chunk_vector` uses the chunk's own `chunk_id` (UUID
string) as the Qdrant point ID directly -- `DocumentChunk.embedding_vector_id`
and a Qdrant point's `id` are the same value *by construction*, never by
a separate lookup that could drift.
**Key concepts a reviewer should understand:**
- `set_document_status` is a plain `UPDATE`, not an upsert -- the
  `Document` row always already exists by the time ingestion runs
  (`POST /documents` is the only thing that ever creates one), so there's
  never a real conflict case, and an upsert would need every other NOT
  NULL column supplied just to satisfy a row-construction path that can
  never actually be taken.
- `ensure_collection()` also creates Qdrant payload indexes
  (`loc_document_id`, `ticker`, `document_type`, `loc_chunk_type`,
  `fiscal_year`, `fiscal_quarter`) -- the concrete delivery on
  `PROJECT_HANDBOOK.md` §2's stated reason for choosing Qdrant ("strong
  native metadata filtering ... alongside vector search"), verified live
  this phase: filtering the collection by `loc_document_id` returned
  exactly the 31 points that document's chunks produced, matching
  Postgres's own count exactly.
- `upsert_chunk_vector` uses `wait=True` -- ingestion is an offline batch
  job, not latency-sensitive, so it's worth blocking until Qdrant
  confirms the write before Postgres records `embedding_vector_id`;
  otherwise a crash between the two writes could leave a `DocumentChunk`
  pointing at a vector that was never actually written.
**Tradeoffs / deliberately left out:** No batched Qdrant upsert (one
`client.upsert()` call per chunk, not one call for the whole document) --
simpler control flow (each chunk's Postgres write and Qdrant write happen
together, in the same loop iteration, so a mid-document crash leaves
clearly-defined "done" vs. "not yet" chunks) at the cost of more HTTP
round-trips; not a problem at this project's document-count scale, worth
revisiting if ingestion throughput ever becomes a bottleneck.
**How it connects to the rest of the system:** Both are called from
`tasks/ingest_document.py`'s per-chunk write loop, immediately after
`SourceLocation` is constructed for that chunk.

---

## [2026-08-09] tasks/ingest_document.py — the real Celery task, replacing Phase 4's no-op
**Phase:** 5 — ingestion pipeline (wiring)
**What was built:** `services/ingestion/src/tasks/ingest_document.py`'s
`ingest_document` task, registered under the same `"ingest_document"`
name as Phase 4's API-side stub. Orchestrates every stage above in order,
assigns each chunk's `chunk_index` (one running counter per page, shared
across narrative/footnote/table chunk types -- the orchestrator is the
only place that sees all three streams merged), builds each chunk's
`SourceLocation` exactly once, and drives `Document.status` through
`PENDING -> PROCESSING -> COMPLETED`/`FAILED`. Uses `autoretry_for`,
`retry_backoff`, and a custom `_StatusTrackingTask.on_failure` so `FAILED`
is only set once Celery has genuinely exhausted retries, not on every
transient attempt.
**Why this approach:** Every chunk's draft content is built (parsing,
segmenting, table extraction, chunking) and embedded in one batched pass
*before* any Postgres/Qdrant write begins -- keeps the two network-bound
external calls (OpenAI, Cohere) out of the write transaction, and means a
failure before that point (a corrupt PDF, an embedding API outage) has
written nothing partial to clean up. `on_failure` (not the task body's
`except` block) is what sets `FAILED`, specifically so the status stays
`PROCESSING` through transient retries -- a Library-page user watching the
status badge sees "Processing" the whole time a retry/backoff cycle runs,
not a flicker back to a stale `FAILED` between attempts.
**Key concepts a reviewer should understand:**
- Task name compatibility with Phase 4's stub was verified *live*, not
  just by matching the string: this phase's smoke test started the real
  worker and it immediately picked up and correctly processed a genuine
  message left in Redis from Phase 4 testing (`document_id=5ff8c29a...`,
  a real PDF uploaded weeks earlier) -- 31 chunks (21 narrative, 4 table,
  6 footnote), 4 tables, all 31 with `embedding_vector_id` populated,
  status flipped `PENDING -> PROCESSING -> COMPLETED`, with zero rename
  or migration needed.
- The retry/backoff/dead-letter path was also verified live and
  unplanned: a second stale queued message referenced a `document_id`
  that no longer exists in Postgres (a deleted/uncommitted test row from
  before this phase). The task retried 3 times with the configured
  exponential backoff (1s, 2s, 3s, matching `docs/architecture.md` §3's
  "retry queue with exponential backoff"), then gave up cleanly --
  `on_failure` ran, attempted to mark that (nonexistent) document
  `FAILED` via a plain `UPDATE` affecting zero rows (not an error), and
  the worker kept running normally afterward. No dead-letter *queue*
  exists (Redis, unlike RabbitMQ, doesn't give one for free) -- the
  `FAILED` Postgres status is the alert surface for now, an accepted gap
  flagged here rather than silently claimed as complete.
- `zip(chunk_specs, embeddings, strict=True)` -- deliberately fails loudly
  if the embedding count ever doesn't match the chunk-spec count, rather
  than silently misaligning a chunk with the wrong vector.
**Tradeoffs / deliberately left out:** `autoretry_for=(Exception,)`
doesn't distinguish retryable failures (a transient Cohere/OpenAI
timeout) from deterministic ones (a genuinely corrupt PDF, a code bug) --
both get the same 3-retry treatment, which is consistent with
`docs/architecture.md` §3's stated behavior for "corrupt or unparseable
PDF" but means a deterministic bug wastes ~3 retry cycles before
surfacing as `FAILED` instead of failing fast. Worth narrowing to
specific exception types if this becomes noisy in practice.
**How it connects to the rest of the system:** The single integration
point every other Phase 5 module was built to be called from. Upstream:
enqueued by `services/api`'s `POST /documents` (Phase 4, unchanged this
phase). Downstream: nothing yet reads its output -- Phase 6's retrieval
pipeline is the first consumer of the `DocumentChunk`/`TableData`/Qdrant
data this task produces.

---

## [2026-08-09] Phase 6 LLM vendor decision: OpenAI for generation/reformulation/expansion
**Phase:** 6 -- retrieval/generation pipeline (setup)
**What was built:** No code -- a recorded decision, asked of Sam directly
before writing `answer_generator.py`, `multi_query.py`, or
`history_manager.py`, since Phase 5's "Provider decisions" entry
explicitly left this open ("Phase 6's `answer_generator.py` will need its
own LLM-provider decision; this entry doesn't presume that one has to be
OpenAI too").
**Why this approach:** Asked as a single question: reuse OpenAI (already
approved in Phase 5 for `agentic_chunker.py`) versus add Anthropic as a
third vendor. Sam chose OpenAI. One vendor relationship now covers
chunking (ingestion) *and* generation/reformulation/expansion (query
pipeline) instead of a third API key/SDK/billing relationship for
marginal differentiation at this project's scale -- consistent with the
same reasoning that put Cohere behind both rerank and embeddings in Phase
5.
**Key concepts a reviewer should understand:**
- This is `CLAUDE.md` §4's stop-and-ask boundary working exactly as
  designed a second time: a real, consequential choice existed (which
  vendor answers every question a user ever asks), it wasn't defensible
  to default silently, so it was asked.
- All three new OpenAI call sites (`multi_query.py`, `history_manager.py`,
  `answer_generator.py`) follow `agentic_chunker.py`'s established
  optional-key/deterministic-fallback contract from Phase 5 -- none of
  them can turn a missing `OPENAI_API_KEY` into a hard failure. See each
  module's own entry below for its specific fallback.
**Tradeoffs / deliberately left out:** `services/api/requirements.txt`
now carries `openai>=1.50` for the first time (previously ingestion-only)
-- not treated as "a new dependency outside the agreed stack" requiring a
fresh check-in, since the vendor itself was already approved project-wide
in Phase 5; only *which service* imports the SDK changed.
**How it connects to the rest of the system:** Governs every OpenAI call
added this phase. `OPENAI_CHAT_MODEL` (default `gpt-4o-mini`, same
default family as ingestion's `OPENAI_CHUNKING_MODEL`) is the one new env
var this decision introduces; `COHERE_RERANK_MODEL` (default
`rerank-v3.5`, `reranker.py`) is the other new optional env var this
phase adds. Both, plus `OPENAI_API_KEY` now being a two-service key, are
documented in `.env.example`.

---

## [2026-08-09] `bm25_retriever.py` + the content full-text-search migration
**Phase:** 6 -- retrieval/generation pipeline
**What was built:** [`core/bm25_retriever.py`](../services/api/src/core/bm25_retriever.py)
-- lexical retrieval over `document_chunks.content` via Postgres's
built-in full-text search (`to_tsvector`/`websearch_to_tsquery`/
`ts_rank_cd`), backed by a hand-written Alembic migration,
[`3100d4408cc5_add_document_chunks_content_fts_index.py`](../migrations/versions/3100d4408cc5_add_document_chunks_content_fts_index.py),
adding a `GIN (to_tsvector('english', content))` index.
**Why this approach:** `PROJECT_HANDBOOK.md` names this module
`bm25_retriever.py`, but the literal Okapi BM25 ranking formula isn't
available from any dependency already in the agreed stack -- getting it
exactly would mean adding `rank_bm25` (an in-memory, un-indexed library
that doesn't scale past a toy corpus) or a real search engine
(Elasticsearch/OpenSearch), both of which are new external services
`CLAUDE.md` §4 requires flagging before adding. Postgres full-text search
needs neither: Postgres is already the agreed relational store, and
`ts_rank_cd` plays the same architectural role BM25 would -- a sparse,
exact-lexical-match signal fused against the dense leg via RRF -- without
a new dependency. This wasn't treated as a stop-and-ask boundary (no new
service was added), but it's still flagged here explicitly since it's a
real substitution worth Sam knowing about, not a hidden implementation
detail: `ts_rank_cd`'s formula (term frequency, proximity, document
length normalization) differs from Okapi BM25's, even though both serve
"sparse lexical retrieval" in the hybrid architecture.
**Key concepts a reviewer should understand:**
- The GIN index is a **functional** index (`to_tsvector('english',
  content)`), not an index on `content` itself -- SQLAlchemy's
  declarative `Column`/`mapped_column` machinery has no construct for
  this, so the migration is hand-written (`op.execute(...)`) rather than
  `alembic revision --autogenerate`'d, the same "autogenerate can't
  express this" situation `8c520544e49c` hit for a different reason
  (enum-type creation) in Phase 4.
- An empty ranked list from `bm25_retriever.search()` isn't an error --
  a query with no lexically-matchable content (e.g. pure stopwords)
  legitimately produces zero full-text hits, and `hybrid_retriever.py`
  treats that as "this leg found nothing," falling back to the dense
  leg alone rather than failing the request.
**Tradeoffs / deliberately left out:** No relevance-tuning beyond
Postgres's defaults (`english` text-search configuration, default
`ts_rank_cd` weighting) -- reasonable to revisit once Phase 8's eval
harness can measure whether lexical-match quality is actually a
bottleneck.
**How it connects to the rest of the system:** One of the two legs
`hybrid_retriever.py` runs in parallel per query variant; its output
feeds `rrf.py`'s fusion alongside `dense_retriever.py`'s.

---

## [2026-08-09] `dense_retriever.py`
**Phase:** 6 -- retrieval/generation pipeline
**What was built:** [`core/dense_retriever.py`](../services/api/src/core/dense_retriever.py)
-- embeds the query text with Cohere (`input_type="search_query"`) and
searches Qdrant's `document_chunks` collection for nearest neighbors via
`query_points`.
**Why this approach:** `input_type="search_query"` is the deliberate,
previously-flagged carry-over from Phase 5 (`docs/progress.md`'s "Phase 5
Immediate Next Step" #2): ingestion embedded every stored chunk with
`"search_document"`, and Cohere's v3 embed models are trained with
different instruction prefixes per `input_type` -- using the wrong one
wouldn't error, it would just measurably hurt retrieval quality. This
module deliberately does **not** import `services/ingestion/src/
embedding/embedder.py`, even though the Cohere call is nearly identical
-- the two services stay decoupled by convention (same model name/env var,
never shared Python code), the same principle Phase 5 established for
`storage/models.py`. `qdrant_client 1.19`'s `query_points` is used
instead of the older `search` method, which this version's client no
longer exposes at all (confirmed via `dir(QdrantClient)` before writing
this, not assumed from older docs).
**Key concepts a reviewer should understand:**
- `get_qdrant_client()` is exported (not `_`-prefixed) specifically so
  `citation_resolver.py` can reuse the same lazily-created client for its
  own, unrelated Qdrant point lookups (recovering a table chunk's
  `table_cell_ref`) -- one shared connection instead of two independent
  ones to the same collection.
- Unlike `reranker.py`, this module has **no fallback** for a missing
  `COHERE_API_KEY` or a failed call -- it raises. There is no meaningful
  dense retrieval without an embedding (mirrors `embedder.py`'s Phase 5
  reasoning for the same asymmetry); `hybrid_retriever.py` is the layer
  that decides a failed dense leg degrades to BM25-only rather than
  failing the whole request, not this module pretending success.
**Tradeoffs / deliberately left out:** No retry/backoff around the Cohere
call itself, matching `embedder.py`'s Phase 5 precedent -- a query-time
Cohere hiccup propagates and `hybrid_retriever.py`'s per-leg guard turns
it into "BM25-only for this request," not a crash.
**How it connects to the rest of the system:** The other leg
`hybrid_retriever.py` runs in parallel with `bm25_retriever.py`.
`citation_resolver.py` also depends on this module, for its shared Qdrant
client, not its retrieval function.

---

## [2026-08-09] `rrf.py`
**Phase:** 6 -- retrieval/generation pipeline
**What was built:** [`core/rrf.py`](../services/api/src/core/rrf.py) --
Reciprocal Rank Fusion, combining any number of independently-ranked
candidate lists into one fused ranking.
**Why this approach:** Fuses by each candidate's **rank position** within
its own list, not by its raw score. This is RRF's entire reason to exist
here, not an oversight: BM25's `ts_rank_cd` output and Qdrant's cosine
similarity live on completely different, incomparable numeric scales --
summing or averaging them directly would let whichever retriever happens
to produce larger raw numbers silently dominate the fusion. `1/(k+rank)`
per list, summed across every list a chunk appears in, is scale-free by
construction, with the standard damping constant (`k=60`, from Cormack,
Clarke & Buettcher 2009) kept as the module's documented default rather
than re-derived.
**Key concepts a reviewer should understand:**
- A chunk found by *both* BM25 and dense retrieval (or by dense retrieval
  across two different multi-query reformulations) accumulates votes from
  every list it appears in -- this is RRF's implicit "independent
  retrievers agreeing on this chunk is itself a signal" behavior, not
  something coded as a special case.
- The only module in the Phase 6 pipeline with zero I/O -- deliberately,
  so it's the cheapest piece to unit-test in isolation
  (`PROJECT_HANDBOOK.md`'s planned `tests/unit/test_rrf.py`).
**Tradeoffs / deliberately left out:** `k=60` is the paper's standard
value, not tuned against this project's own retrieval distribution --
Phase 8's eval harness is the right place to check whether a different
`k` measurably changes retrieval precision here.
**How it connects to the rest of the system:** Called by
`hybrid_retriever.py`, once per query, over every BM25/dense list pair
collected across all of `multi_query.py`'s expanded query variants.

---

## [2026-08-09] `hybrid_retriever.py`
**Phase:** 6 -- retrieval/generation pipeline
**What was built:** [`core/hybrid_retriever.py`](../services/api/src/core/hybrid_retriever.py)
-- runs BM25 + dense retrieval concurrently for every query variant
passed in, fuses everything via `rrf.py`, then hydrates the fused top-N
chunk_ids into full `RetrievedChunk`s with one batched Postgres query
(joining `Document`/`Company`/`TableData`).
**Why this approach:** `retrieve()` takes a *list* of query texts, not
one, so a single function serves both the plain-query path and
`multi_query.py`'s expanded-query path uniformly -- every variant just
contributes one more BM25 list and one more dense list into the same RRF
fusion, rather than multi-query needing a separate fusion-of-fusions
step. The two legs run in a 2-worker `ThreadPoolExecutor` per variant --
this is safe despite SQLAlchemy's `Session` not being safe for
*concurrent* use, because `db` (used only by the BM25 leg) is never
touched by more than one thread at a time: the calling thread blocks on
`.result()` rather than touching `db` while the worker thread has it,
so it's sequential handoffs across threads, not true concurrent access.
Both legs are wrapped to catch, log, and degrade to an empty list rather
than propagate -- a down/misbehaving retriever leg shouldn't 500 the
whole request when the other leg alone is still a usable, if weaker,
result.
**Key concepts a reviewer should understand:**
- Hydration is a single `chunk_id IN (...)` query for the *fused,
  trimmed* candidate set, never for raw per-leg candidates -- most of the
  ~30-per-leg raw candidates never survive RRF fusion into the ~20 that
  get hydrated, so this is where the expensive joined Postgres read
  (`TableData.raw_table_json` in particular, needed later by
  `numeric_verifier.py`) is deliberately deferred to.
- `bm25_score`/`dense_score` on the returned `RetrievedChunk`s are only
  ever populated from `query_variants[0]` (the primary/original
  question) -- a per-expansion-variant score isn't a meaningful thing to
  show or log per chunk, so only the primary query's own leg scores are
  kept for observability.
**Tradeoffs / deliberately left out:** `_RETRIEVE_TOP_N`/leg `top_k`
values (30 per leg, 20 fused) are picked by inspection, not tuned against
eval data -- flagged here and again in `query.py`'s entry as a concrete
Phase 8 follow-up.
**How it connects to the rest of the system:** The single entry point
`api/v1/routes/query.py` calls for retrieval; internally composes
`bm25_retriever.py`, `dense_retriever.py`, and `rrf.py`. Its output feeds
`reranker.py`.

---

## [2026-08-09] `reranker.py`
**Phase:** 6 -- retrieval/generation pipeline
**What was built:** [`core/reranker.py`](../services/api/src/core/reranker.py)
-- Cohere rerank (`rerank-v3.5`) over the RRF-fused candidates, populating
`rerank_score` and returning the top N.
**Why this approach:** This is the concrete case `PROJECT_HANDBOOK.md` §2
names for why Cohere rerank is in the stack at all: the same metric
("data center revenue") can appear near-identically worded across several
quarters' filings, and pure vector similarity can't distinguish "the
quarter this question is actually about" from "a quarter that happens to
use similar words" -- a cross-encoder scoring the *actual query text*
against each candidate can. Falls back to the incoming RRF order (no
Cohere call at all) if `COHERE_API_KEY` is unset or the call fails --
deliberately a different failure mode than `dense_retriever.py`'s hard
requirement: reranking is a quality refinement on top of retrieval that
already succeeded, so skipping it degrades ranking quality, not
correctness. Matches the "optional-quality provider call, deterministic
fallback" pattern `agentic_chunker.py` established in Phase 5.
**Key concepts a reviewer should understand:**
- The text sent to Cohere per candidate is `content` prefixed with a
  light metadata header (ticker/document type/page) -- rerank benefits
  from that signal too (e.g. telling apart near-identical text from two
  different companies' filings), not just the raw passage.
- Verified live against the real Cohere API this phase (see `docs/
  progress.md`'s snapshot) -- a real question against the real ingested
  Acme 10-K correctly ranked its own segment-revenue table above three
  unrelated candidates, with a rerank score of ~0.90.
**Tradeoffs / deliberately left out:** No caching of rerank results --
each query pays a fresh Cohere rerank call even for a repeated question;
`docs/architecture.md` §"Deployment Handbook"'s note on caching frequent
queries (filings update quarterly, so aggressive caching is safe) is a
Phase 9 concern, not addressed here.
**How it connects to the rest of the system:** Takes `hybrid_retriever.py`'s
output, called from `api/v1/routes/query.py`; its output (the final
context) feeds `answer_generator.py`, `numeric_verifier.py`, and
`citation_resolver.py` directly.

---

## [2026-08-09] `multi_query.py`
**Phase:** 6 -- retrieval/generation pipeline
**What was built:** [`core/multi_query.py`](../services/api/src/core/multi_query.py)
-- OpenAI-generated alternative phrasings of the (already history-
reformulated, if applicable) question, up to 2 beyond the original, fed
into `hybrid_retriever.py` as additional query variants.
**Why this approach:** Runs *after* `history_manager.py`'s reformulation,
never before -- expanding a follow-up fragment like "what about margins?"
into several phrasings of the same ambiguous fragment wouldn't improve
recall, it would just multiply the ambiguity. Capped at 2 extra variants
deliberately small: each variant costs one more full BM25+dense retrieval
pair in `hybrid_retriever.py`, and this project's differentiator is
grounded, verifiable answers, not maximal recall at any latency/cost.
Falls back to `[query_text]` (no expansion) on a missing key or any
failure -- expansion is a pure recall improvement, not correctness-
critical, since `hybrid_retriever.py` always runs the original query's
own legs regardless of whether expansion succeeded.
**Key concepts a reviewer should understand:**
- JSON-mode response format (`response_format={"type": "json_object"}`),
  same pattern `agentic_chunker.py` used in Phase 5 for structured LLM
  output, parsed defensively (a malformed/empty `variants` list just
  falls through to the original query only).
**Tradeoffs / deliberately left out:** No de-duplication check between a
generated variant and the original query text beyond what the LLM itself
avoids via the system prompt -- an accidental near-duplicate variant just
means one of `hybrid_retriever.py`'s BM25/dense pairs is redundant, not
wrong.
**How it connects to the rest of the system:** Its output is
`query.py`'s `expanded_queries`, passed straight into
`hybrid_retriever.retrieve()`.

---

## [2026-08-09] `history_manager.py`
**Phase:** 6 -- retrieval/generation pipeline
**What was built:** [`core/history_manager.py`](../services/api/src/core/history_manager.py)
-- rewrites a follow-up question into a self-contained one using an
OpenAI call over the conversation's prior turns (most recent 6 kept).
**Why this approach:** "What about their margins?" shares almost no
retrievable vocabulary with the source text it needs to match --
`hybrid_retriever.py` searching on that fragment literally would likely
retrieve nothing useful. Reformulating it into "What were NVIDIA's gross
margins in Q4 FY24?" first is what makes retrieval possible at all for a
follow-up. Unlike `multi_query.py`'s pure-recall tradeoff, skipping this
(no `OPENAI_API_KEY` / a failed call) has a real retrieval-quality cost,
not just a smaller candidate pool -- accepted anyway for the same reason
Phase 5 accepted `agentic_chunker.py`'s heuristic fallback: a degraded
question is still a real, answerable-if-weaker request, not a system
failure. Verified live this phase without an `OPENAI_API_KEY` configured:
a real follow-up ("What about their revenue growth?") retrieved
genuinely relevant chunks from the un-reformulated fragment alone, just
with a lower Cohere rerank score (~0.32) than the initial, well-formed
question (~0.90) -- exactly the retrieval-quality cost this entry
describes, visible end-to-end via `confidence_scorer.py`'s
`low_confidence` flag rather than a silent quality loss.
**Key concepts a reviewer should understand:**
- `prior_turns` is `[(query_text, answer_text), ...]` in the order
  actually asked -- sourced in `query.py` from `Conversation.queries`'
  existing `order_by="Query.created_at"` relationship (Phase 2), not
  re-derived here.
- `reformulated_query_text` (the `Query` row's own column, populated only
  for follow-ups) is set to `None` when reformulation returns the
  follow-up text unchanged, not the unchanged text itself -- preserves
  the column's Phase 2-documented meaning ("populated only when
  reformulation actually rewrote something").
**Tradeoffs / deliberately left out:** No conversation summarization for
threads longer than 6 turns -- older turns are simply dropped from the
prompt, not summarized, since a follow-up almost always refers to recent
context and full summarization is out of Phase 6's scope.
**How it connects to the rest of the system:** Called only from
`api/v1/routes/query.py`'s `submit_followup_query`; its output becomes
`retrieval_query_text`, driving `multi_query.py`,
`hybrid_retriever.py`, and `answer_generator.py` for that request.

---

## [2026-08-09] `answer_generator.py`
**Phase:** 6 -- retrieval/generation pipeline
**What was built:** [`core/answer_generator.py`](../services/api/src/core/answer_generator.py)
-- grounded OpenAI generation over the reranked context, with every claim
required (by prompt) to carry a `[n]` citation marker matching the
1-based position of the context item it's drawn from; falls back to a
zero-synthesis **extractive** answer (the raw content of the top 3
reranked chunks, tagged with citation markers) when there's no
`OPENAI_API_KEY` or the call fails.
**Why this approach:** The extractive fallback is a deliberately stronger
guarantee than `multi_query.py`/`history_manager.py`'s fallbacks: because
it can only ever contain text that was literally copied from a cited
source, it's trivially grounded by construction, with nothing for
`numeric_verifier.py` to actually catch as wrong -- it can be a *worse*
answer (no synthesis, no natural-language framing, a raw table dump reads
poorly), but never a *less-grounded* one. This was this session's actual
integration-test path: `OPENAI_API_KEY` is unset in this environment (see
`docs/progress.md`'s Phase 5 snapshot), so every live query run this
phase exercised the extractive fallback, not the LLM path -- confirmed
working end-to-end (screenshot-verified through the real Chat UI) even in
that degraded mode.
**Key concepts a reviewer should understand:**
- The system prompt's rule 3 ("copy numeric figures exactly ... do not
  round, recompute, or convert units") exists specifically so
  `numeric_verifier.py`'s comparison has a fighting chance -- a model
  that "helpfully" reformats `$18.4 billion` as `$18,400M` would still be
  correct, but harder to verify string-for-string; the rule reduces that
  friction without `numeric_verifier.py` needing to be perfect at
  catching every reformatting.
- `chunks` is always exactly what `reranker.py` returned, in that exact
  order -- this module never re-sorts or filters it, since the `[n]`
  marker numbering promise (shared with `numeric_verifier.py` and
  `query.py`'s marker-renumbering step) depends on that order staying
  stable end-to-end.
**Tradeoffs / deliberately left out:** No streaming -- a full
`chat.completions.create` call, not `stream=True`, since Phase 6 has no
SSE/websocket plumbing in `query.py`'s FastAPI routes yet; the Chat UI's
loading state is a simple spinner, not token-by-token rendering.
**How it connects to the rest of the system:** Consumes `reranker.py`'s
output; its `answer_text` feeds `numeric_verifier.py` (verification) and
(after `query.py`'s marker renumbering) becomes `Answer.answer_text`.

---

## [2026-08-09] `numeric_verifier.py`
**Phase:** 6 -- retrieval/generation pipeline
**What was built:** [`core/numeric_verifier.py`](../services/api/src/core/numeric_verifier.py)
-- the literal implementation of `CLAUDE.md` §1's core promise: every
numeric claim in the generated answer, checked against the exact source
chunk/table its citation marker points to. Pure regex + arithmetic, no
LLM call anywhere in it.
**Why this approach:** Verifying a number by asking another LLM "does
this look right?" would just trade one hallucination-shaped risk for
another -- a verifier model can be wrong or sycophantic too. This module
is deterministic on purpose: extract numbers from the claim's text
window (the text immediately preceding its `[n]` marker), extract numbers
from citation `n`'s actual source content, check for a real numeric
match. The one genuinely hard sub-problem this surfaced: financial prose
and financial tables don't use the same scale convention for "the same"
number -- a table cell under a "Revenue ($B)" header might just say
`18.4`, while generated prose might say "$18.4 billion" *or*, just as
validly, "$18,400 million." Comparing only scaled values would wrongly
fail the first case; comparing only raw digits would wrongly fail the
second. `_matches()` tries all four raw/scaled combinations
(claim-raw vs. source-raw, claim-scaled vs. source-raw, claim-raw vs.
source-scaled, claim-scaled vs. source-scaled) rather than picking one
convention and hoping the source happens to match it.
**Key concepts a reviewer should understand:**
- `has_scale_signal` (a `$`, `%`, decimal point, comma-thousands
  separator, or a scale word) is what separates a "claim worth
  verifying" from noise -- bare small integers like "4" in "last 4
  quarters" or "2024" in a fiscal year reference are never treated as
  numeric claims needing traceability; they're not the kind of figure
  this project's guarantee is about, and flagging them would be pure
  noise against the confidence score.
- For `TABLE` chunks, source numbers are pulled from the *complete*
  `TableData.raw_table_json` (headers + every row), never from
  `DocumentChunk.content` -- that column holds only a 5-sample-row
  embedding-summary string for table chunks (`table_chunker.py`'s
  `_embedding_text`, Phase 5), and verifying against it would falsely
  flag a correct number drawn from row 6+ as unsupported.
- Verified live this phase against the real Acme 10-K's segment-revenue
  table (`$120.4M`/`$171.3M`/etc. across 4 quarters x 3 segments) and,
  separately, against 58 real numeric claims extracted from a genuine SEC
  filing's disaggregated-revenue table (multi-million-dollar figures with
  comma separators, parenthesized negative percentages) -- all verified
  correctly, confirming the four-way matching actually holds up against
  real, not synthetic, financial-table formatting. (A debugging session
  did surface a self-inflicted bug in a throwaway verification script,
  not this module -- feeding chunks back in the wrong order produced
  false "unverified" results; re-run with correct ordering, matching
  exactly how `query.py` actually calls this module, showed zero false
  negatives.)
**Tradeoffs / deliberately left out:** Tolerance is `rel_tol=0.02,
abs_tol=0.05` (2% relative / small absolute) -- accepts minor rounding
noise between a source's exact figure and a model's restated one, but
isn't validated against a labeled mismatch set; Phase 8's eval harness is
the right place to check whether this tolerance is too loose or too
strict in practice. No handling of written-out number words ("eighteen
point four billion") -- only digit-based figures are extracted.
**How it connects to the rest of the system:** Takes `answer_generator.py`'s
output and `reranker.py`'s chunk list (matched positionally by marker
number); its `NumericClaimResult` list feeds `confidence_scorer.py`
directly and is never itself persisted.

---

## [2026-08-09] `confidence_scorer.py`
**Phase:** 6 -- retrieval/generation pipeline
**What was built:** [`core/confidence_scorer.py`](../services/api/src/core/confidence_scorer.py)
-- combines a pre-generation retrieval-confidence signal (top rerank
score, or a saturating function of the top RRF score if rerank was
skipped) with `numeric_verifier.py`'s results into one final
`confidence_score` + `low_confidence` flag.
**Why this approach:** A single unverified numeric claim caps confidence
hard (`min(retrieval_conf, 0.35) * verification_rate`), rather than being
averaged away against several correct claims and a strong retrieval
score. This is a direct expression of `CLAUDE.md` §1's numeric-
traceability promise at the scoring layer: a plausible-sounding answer
with even one wrong number is not a confident answer, no matter how
relevant retrieval looked. Verified live this phase against real data in
both directions -- a well-grounded table answer scored 0.90 (high rerank
score, all numeric claims self-verified), a vague, un-reformulated
follow-up scored 0.32 (numeric claims all verified, but the top rerank
score itself was genuinely low), and a nonsense out-of-corpus query
scored 0.02 (correctly near-zero without needing a hard pre-generation
block at all -- see `query.py`'s entry).
**Key concepts a reviewer should understand:**
- The RRF-score fallback (`_RRF_SATURATION_SCORE = 0.05`) is a crude,
  explicitly-labeled normalization for the "rerank was skipped" case
  only -- an RRF-fused score is an unbounded sum of `1/(k+rank)` terms
  (see `rrf.py`), not a 0..1 similarity, so it can't be compared to
  Cohere's rerank score on the same scale; this is a deliberately
  separate code path, not a shared formula.
**Tradeoffs / deliberately left out:** `LOW_CONFIDENCE_THRESHOLD = 0.4`
and the `0.35` unverified-claim ceiling are both calibrated by inspection
against this phase's live tests, not against Phase 8's (not-yet-built)
gold eval set -- flagged as a concrete Phase 8 follow-up: revisit both
constants once there's a labeled dataset to check them against instead of
three manually-inspected examples.
**How it connects to the rest of the system:** `retrieval_confidence()`
is read by `query.py` before generation runs (informationally, not as a
hard gate -- see that entry); `score_final()` runs after
`numeric_verifier.py` and produces the `confidence_score`/`low_confidence`
values written to `Answer` and returned in `QueryResponse`.

---

## [2026-08-09] `citation_resolver.py`
**Phase:** 6 -- retrieval/generation pipeline
**What was built:** [`core/citation_resolver.py`](../services/api/src/core/citation_resolver.py)
-- maps a cited `RetrievedChunk` back to its `SourceLocation`
(`packages/shared`), the read-path counterpart to what
`tasks/ingest_document.py` builds at write time (Phase 5).
**Why this approach:** For `NARRATIVE`/`FOOTNOTE` chunks, every field
`SourceLocation` needs already lives on the Postgres row -- no I/O. For
`TABLE` chunks, `table_cell_ref` (e.g. `"table 0"`) was **only ever
written into Qdrant's payload** at ingestion time
(`tasks/ingest_document.py`'s `SourceLocation(...)` construction); it
does not exist anywhere in Postgres. Rather than re-deriving or guessing
it here -- which would quietly violate `docs/architecture.md` §2's "never
regenerated or re-derived" the moment ingestion's table-indexing logic
ever changed -- this module fetches the chunk's own Qdrant point by ID
(`chunk_id` *is* the Qdrant point ID, by construction; `qdrant_writer.py`,
Phase 5) and reconstructs the exact `SourceLocation` ingestion originally
wrote, via `SourceLocation.from_qdrant_payload` -- the read-side
counterpart Phase 5 built specifically for this moment, previously
unexercised by any code (`docs/DECISIONS_LOG.md`'s Phase 5 entry for
`source_location.py` calls this out explicitly: "Not exercised by
anything in Phase 5 ... included now so the shape is symmetric"). This is
also why a BM25-only retrieval hit for a table chunk (Postgres has no
Qdrant payload attached to it) still resolves a fully correct citation:
the lookup happens here, uniformly, regardless of which retriever
originally surfaced the chunk. Verified live this phase: a real query
against the Acme 10-K's table chunk resolved `exact_location = "p.3
(table 0)"`, confirmed correct via the Chat UI's citation panel
screenshot.
**Key concepts a reviewer should understand:**
- `_fallback_source_location()` (an explicit `"table (unresolved)"`
  marker, not a guess) is reached only if the Qdrant point lookup itself
  fails or returns no payload -- a genuinely rare race (the point's write
  never completed, or was later deleted), not the common path.
- `build_snippet()` also lives here, not on the `Citation` model or in
  `query.py` -- it's conceptually part of "what does this citation show
  a user," the same responsibility as resolving its location.
**Tradeoffs / deliberately left out:** One Qdrant round-trip per cited
table chunk per request (not batched) -- acceptable because it only runs
for the small number of chunks that made it into a *final answer's*
citations (typically 1-3), never for raw retrieval candidates.
**How it connects to the rest of the system:** Called from `query.py`
for each actually-cited chunk, to build both `Citation.exact_location`
and `Citation.snippet` before persisting.

---

## [2026-08-09] `CitationResponse` display fields + `get_or_create_actor` + real `POST /query`/`POST /query/followup`
**Phase:** 6 -- retrieval/generation pipeline
**What was built:** [`api/v1/routes/query.py`](../services/api/src/api/v1/routes/query.py)
-- the real pipeline wiring, replacing Phase 3's stubs, shared between
both routes via `_handle_query`. [`api/v1/deps.py`](../services/api/src/api/v1/deps.py)
gains `get_or_create_actor()`. [`models/schemas/citation.py`](../services/api/src/models/schemas/citation.py)'s
`CitationResponse` gains `document_title`/`document_type`/`ticker`/
`page_number`/`fiscal_year`/`fiscal_quarter`.
**Why this approach:**
- **`get_or_create_actor`:** Phase 6 is the first phase that needs a
  real, persisted `User` row -- a `Conversation.user_id` FK has to point
  at something that actually exists, but there's still no real auth and
  no seed script ever populated `organizations`/`users`
  (`scripts/seed_dev_data.py`, Phase 4, only seeded `Company`/`Document`).
  Rather than block Phase 6 on building real auth (far out of scope) or
  inventing a differently-shaped workaround, this reuses the exact
  find-or-create pattern `documents.py` already established for `Company`
  in Phase 4, one level up the hierarchy (`Organization` under
  `PLACEHOLDER_ORG_ID`, then a well-known placeholder `User` under it).
- **Citation marker renumbering (`_renumber_markers`):** `citations` in
  the response only contains chunks the answer *actually* cited, which
  can be a strict subset of what was offered as context (e.g. the model
  cites `[1]` and `[4]`, skipping `[2]`/`[3]`) -- without renumbering,
  `citations[1]` (index 1) wouldn't correspond to marker `[4]`, and a
  frontend would need a separate lookup mechanism to resolve a click.
  Rewriting markers to be contiguous (`[1]`, `[2]`, ...) *before*
  persisting `Answer.answer_text` means `citations[i]` always is the
  `(i+1)`-th marker as it literally appears in the stored/returned text
  -- no extra index field needed on `CitationResponse` for the frontend
  to resolve a click, just `citations[n - 1]`.
- **No separate pre-generation confidence gate:**
  `docs/architecture.md` §3 frames "retrieval confidence above
  threshold?" as a branch before generation runs at all.
  `answer_generator.generate_answer([])` already returns a safe "not
  enough information" message when `reranked` is empty -- the one case
  actually worth gating on. An arbitrary numeric threshold between
  "clearly irrelevant" and "borderline" isn't something to hardcode
  without eval data to calibrate it against (Phase 8's job); verified
  live this phase that a genuinely nonsense query still produces a safe,
  correctly near-zero-confidence response without a hard gate (see
  `confidence_scorer.py`'s entry) -- the post-generation
  `confidence_score`/`low_confidence` signal does the "treat this
  cautiously" job instead.
- **`CitationResponse`'s new fields are populated by hand, not via
  `model_validate(citation_orm)`** -- they don't live on the `Citation`
  ORM row at all (sourced from the cited chunk's `Document`/`Company`
  instead), so the route builds each `CitationResponse` explicitly from a
  `(Citation, RetrievedChunk)` pair. `citations.py`'s still-stubbed route
  (out of Phase 6's scope) needed a small matching update -- placeholder
  values for the new required fields -- purely to keep constructing
  correctly, not a real implementation of that route.
**Key concepts a reviewer should understand:**
- `submit_query` never reformulates, even when `conversation_id` is
  passed -- per `QueryRequest`'s existing Phase 3 docstring, that's
  `/query/followup`'s job specifically. A conversation's *first* message
  always goes through `submit_query`.
- Three `db.flush()` calls (`Query` -> `Answer` -> `Citation` rows), one
  final `db.commit()` -- each flush exists only to assign the next row's
  FK target, matching the `Company`-then-`Document` flush pattern
  `documents.py` established in Phase 4.
- `Conversation`/`Query` 404 handling checks `conversation.user_id ==
  actor.user_id` -- always true today (one placeholder user), but real
  multi-tenant hygiene once real auth exists, not dead code.
**Tradeoffs / deliberately left out:** `_RETRIEVE_TOP_N=20`/
`_RERANK_TOP_N=6` are picked by inspection (same caveat as
`hybrid_retriever.py`'s per-leg `top_k` values) -- a concrete Phase 8
follow-up, not tuned against eval data yet.
**How it connects to the rest of the system:** The one integration point
every Phase 6 `core/` module was built to be called from, in the exact
pipeline order documented in this file's module docstring. Live-verified
this phase against real ingested data (a synthetic Acme 10-K with a real
table, a real downloaded ESOA SEC 10-K with 284 real chunks) via direct
API calls and, separately, through the real Chat UI end-to-end
(screenshots: a numeric answer with a correctly-resolved `p.3 (table 0)`
citation matching the source table exactly).

---

## [2026-08-09] `frontend/src/app/lib/api.ts` + `frontend/src/app/pages/Chat.tsx` wired to the real query pipeline
**Phase:** 6 -- retrieval/generation pipeline
**What was built:** `api.ts` gains `CitationRecord`/`QueryRecord` types
and `submitQuery`/`submitFollowupQuery`, mirroring `query.py`'s schemas.
`Chat.tsx` replaces the hardcoded `MOCK_CITATIONS` and static example
Q&A with real conversation state (`messages`, `conversationId`), calling
the real API and rendering the real response.
**Why this approach:** A conversation already in progress always calls
`/query/followup`, never `/query` again -- once `conversationId` is set
from the first response, every subsequent message in that thread is, by
definition, a follow-up that should get history-aware reformulation; only
the very first message in a thread has no history to reformulate against,
so it goes to plain `/query`. `[n]` markers inside `answer_text` are
parsed client-side (`text.split(/(\[\d+\])/g)`) and rendered as clickable
badges resolved via `citations[n - 1]` -- safe specifically because
`query.py`'s marker renumbering guarantees that positional mapping always
holds (see that entry); without it, this would need to search `citations`
by some other key. Each badge, on click, maps a `CitationRecord` onto
`Layout.tsx`'s existing `Citation` shape and reuses its already-built
"Source Citation" side panel -- no changes needed there.
**Key concepts a reviewer should understand:**
- The empty-conversation-thread branch (`activeProject.isEmpty`) is
  untouched -- `Project`/`activeProject` are pure frontend/mock state
  (no backend `Project` entity exists, and Phase 4 already established
  documents are a shared corpus, not project- or org-scoped), so that
  branch stays exactly as decorative as it was before this phase.
- `low_confidence` renders as an inline amber warning per assistant
  message (reusing the existing `AlertTriangle` styling from the old
  mock markup), and every assistant message shows its numeric
  `confidence_score` as a percentage badge -- the UI surface for
  `docs/architecture.md` §3's "tag the response as low-confidence so the
  UI can surface a warning" requirement.
- Verified with a real headless-browser run (Playwright, driven via a
  scratch script since no `chromium-cli`/project run-skill exists yet for
  this repo) against the real dev server and the real API on real
  ingested data -- not just `npm run build` succeeding. Screenshots
  confirm: the typed question, the rendered answer with two live
  citation badges, and the citation side panel showing the correct
  document title/type/ticker/page and an extract matching the source
  table's Q4 2025 Data Center revenue figure exactly.
**Tradeoffs / deliberately left out:** No streaming/typing-indicator
beyond a static spinner (`answer_generator.py` doesn't stream either --
see that entry). No retry-on-failure UI beyond a plain error banner. No
`tsconfig.json` exists yet for this frontend (flagged since Phase 1), so
none of this was type-checked by `tsc` -- only by `vite build` (real
esbuild transpilation + bundling, which does fail on unresolved imports
and syntax errors) and the live browser run.
**How it connects to the rest of the system:** The last piece of Phase
6's "ask a real question in the Chat UI ... get back an answer with
citations pointing to a real page number" Definition of Done
(`PROJECT_HANDBOOK.md` §6) -- confirmed live, not just by code reading.

---

## [2026-08-09] `numeric_verifier.py` bugfix: uncited trailing claims were invisible, not just unverified
**Phase:** 6 -- retrieval/generation pipeline (fix, found after adding a
real `OPENAI_API_KEY`)
**What was built:** A fix to
[`numeric_verifier.verify_answer`](../services/api/src/core/numeric_verifier.py)
-- text *after* the last `[n]` citation marker (or the whole answer, if
it has no markers at all) is now scanned for numeric claims too, and any
found are recorded as automatic, unverified failures (`citation_index=0`
sentinel) instead of being silently skipped.
**Why this approach:** Every live test up to this point in Phase 6 ran
without `OPENAI_API_KEY` configured, so `answer_generator.py` only ever
exercised its extractive fallback -- which, by construction, never
produces trailing uncited text (every fallback line ends in its own
`[n]`). The moment Sam added a real key and the LLM generation path ran
for the first time, a real model did something the extractive fallback
structurally can't: it answered "$171.3M ... $120.4M ... an increase of
$50.9M" and cited the first two figures but not the third, computed one
-- a completely ordinary thing for an LLM to do, and exactly the failure
mode `CLAUDE.md` §1 exists to catch. `verify_answer`'s original loop only
ever looked at the text *preceding* each marker, so a claim with no
marker following it wasn't failing verification, it was **never being
looked at**, and the response came back at 0.93 confidence -- high
confidence, silently wrong. Caught immediately by re-running the exact
same live query that had just been used as this phase's positive
example, not by a planned test case; re-verified with a corrected debug
script and a live re-run afterward, both confirming the fix: the same
query now correctly returns confidence 0.23, `low_confidence: true`.
**Key concepts a reviewer should understand:**
- The fix's framing matters: "verified" means *traceable to a source*,
  not *arithmetically correct*. $171.3M - $120.4M does equal $50.9M --
  the model wasn't wrong, but the number wasn't grounded in anything the
  system can point a citation at, and this project's numeric-
  traceability promise is specifically about groundedness, not just
  correctness. A number a user can't click through to a source is, for
  this project's purposes, not a confident claim, even when it happens
  to check out.
- This is a strong argument for why this project's live-testing
  discipline (real infra, real ingested data, re-running the exact query
  that just "worked") matters more than it might look like from the
  outside: a synthetic/mocked test for this module would have had to
  specifically construct an uncited-trailing-claim answer to catch this;
  a real model, asked a real comparison question, produced one on its
  own, on the very first LLM-backed query this phase ever ran.
**Tradeoffs / deliberately left out:** No attempt to check an uncited
trailing claim against the *union* of all cited chunks' source text (the
more lenient alternative) -- an uncited claim is unverifiable by
definition regardless of whether the number happens to appear somewhere
in the context; the strict interpretation was chosen deliberately, not
by default.
**How it connects to the rest of the system:** Directly changes
`confidence_scorer.score_final`'s input for any answer with this shape;
retroactively also applies to every already-shipped call site
(`answer_generator.py`'s LLM path and its extractive fallback both flow
through this function unchanged).

---

## [2026-08-09] Compare backend: `GET /compare/metric` and `metric_comparator.py`
**Phase:** 7 -- remaining pages (Compare, Admin)
**What was built:** A new
[`core/metric_comparator.py`](../services/api/src/core/metric_comparator.py)
that finds the same table row (a "metric," e.g. "Revenue") across every
`COMPLETED` document ingested for one company, plus a new
[`GET /compare/metric`](../services/api/src/api/v1/routes/compare.py)
route and [`compare.py`](../services/api/src/models/schemas/compare.py)
schema exposing it. This is what `docs/architecture.md` §8 UC5 ("Compare
metrics across quarters") and `PROJECT_HANDBOOK.md`'s Phase 7 prompt
("pulls the same metric across multiple ingested quarters/documents for a
company") actually resolve to in code.
**Why this approach:** The matching itself is a case-insensitive
substring match against each `TableData.raw_table_json` row's first cell,
not an LLM/embedding lookup. A real financial table's row already carries
the metric name as its first cell (e.g. `"Revenue"`, `"Net income"`) by
construction of `table_extractor.py`'s never-flatten extraction (Phase
5) -- the same reasoning `numeric_verifier.py` already established for
this project (`CLAUDE.md` §1: prefer a boring, deterministic check over
trading one hallucination-shaped risk for another). "First match wins"
per document (not "best match" / ranked) was a deliberate simplification:
a filing's primary income-statement table almost always appears before
segment/footnote-detail tables that might reuse the same label, so
first-match already picks the right section in the common case, and
there's no gold set yet (that's Phase 8's job) to validate a smarter
ranked match against. `exact_location` is resolved by building a
`RetrievedChunk` from the matched `DocumentChunk` and reusing
`citation_resolver.resolve_source_location` -- one Qdrant lookup per
matched document -- rather than hand-rolling a second, possibly
inconsistent location-string format; Compare's citations now look and
resolve identically to Chat's.
**Key concepts a reviewer should understand:**
- `headers`/`values` travel to the frontend as parallel lists, never a
  flattened string -- same "never flatten a table" principle as
  `TableData.raw_table_json` itself, so a filing with a different column
  structure (e.g. a comparative prior-year column) than another filing
  doesn't get forced into a fake shared shape.
- A 404 (`ticker` matches no ingested `Company`) is a genuinely different
  response than a 200 with `periods: []` (`ticker` exists, `metric`
  matched nothing anywhere) -- the frontend needs to tell "wrong ticker"
  apart from "right ticker, metric not found," so this isn't collapsed
  into one "not found" case.
- `Document.chunks.and_(DocumentChunk.chunk_type == ChunkType.TABLE)`
  (SQLAlchemy's `WITH LOADER CRITERIA`-backed relationship filtering) is
  used so only table chunks get eager-loaded per document, instead of
  hydrating every narrative/footnote chunk just to filter them out in
  Python.
- Not tenant-scoped, matching `documents.py`'s Phase 4 precedent:
  `Document`/`Company` are shared reference data (public SEC filings),
  with no relationship to `Organization` in the ER model.
**Tradeoffs / deliberately left out:** Live-verified against real
ingested data, but the two real-data fixtures currently in Postgres don't
exercise the "same metric across *multiple separate documents*" case end
to end: Acme Robotics' one synthetic 10-K has a single table shaped
segment-rows x quarter-columns (all four quarters already in one table,
one document), and the real downloaded Energy Services of America 10-K
has zero extracted tables at all (a pre-existing Phase 5 gap --
`camelot`/`layout_segmenter.py` didn't flag any table candidate pages on
that particular PDF; not something this phase's scope covers fixing).
What *is* live-verified end to end: searching `ticker=ACME,
metric=Data+Center` correctly matches the "Data Center" row, returns its
real quarter-by-quarter values, and resolves a real `exact_location`
(`p.3 (table 0)`) via a real Qdrant lookup -- the full mechanism works;
demonstrating true multi-document quarter-over-quarter comparison just
needs more than one ingested filing per company with income-statement-
shaped tables, which the current dev-data doesn't have yet.
**How it connects to the rest of the system:** Reuses
`core/citation_resolver.py` and `core/types.RetrievedChunk` from Phase 6
rather than duplicating chunk-hydration/location-resolution logic;
consumed by the Compare page (see the paired frontend entry below).

---

## [2026-08-09] Admin backend: real `GET /admin/analytics` and `GET /admin/flagged-answers`
**Phase:** 7 -- remaining pages (Compare, Admin)
**What was built:** Rewrote
[`api/v1/routes/admin.py`](../services/api/src/api/v1/routes/admin.py)
and its [schemas](../services/api/src/models/schemas/admin.py) to compute
real KPI counters, a 7-day query-volume-vs-flagged-responses series, a
most-cited-companies panel, and the flagged-answers review table from
actual `Document`/`Conversation`/`Query`/`Answer`/`Citation`/`EvalResult`
rows, replacing Phase 3's all-zero/empty placeholders.
**Why this approach:** "Flagged" is defined as one `OR` of two signals,
factored into a single `_flagged_condition()` helper reused by both
routes: `Answer.confidence_score` below the *same*
`LOW_CONFIDENCE_THRESHOLD` constant the live query pipeline already uses
(`core/confidence_scorer.py`) -- imported, not re-declared, so the two
can't silently drift apart -- OR a linked `EvalResult.flagged_by_human =
True`. `EvalResult` rows don't exist yet (Phase 8's eval harness is the
only writer, and Phase 8 hasn't been built), so today every flagged row
reaches these endpoints via the confidence path; the human-review path is
wired in now anyway so the query/filter shape doesn't need to change the
moment Phase 8 starts writing `EvalResult` rows. Tenant scoping is
deliberately inconsistent *by design*, not an oversight:
`Conversation`/`Query`/`Answer`/`EvalResult` are scoped by `tenant.org_id`
(joined through each `Conversation`'s owning `User`) because those tables
genuinely belong to an organization in the ER model, while
`total_documents`/`indexed_document_count` are not scoped, mirroring
`documents.py`'s Phase 4 precedent that the filing corpus is shared
reference data.
**Key concepts a reviewer should understand:**
- "Top Query Topics" (the original frontend mock) was deliberately
  replaced with "Most-Cited Companies," backed by a real `GROUP BY
  Company.ticker` over `Citation` rows. Real topic modeling would need a
  new dependency (an embedding-clustering library, or a dedicated LLM
  call) not already in the agreed stack (`CLAUDE.md` §3); which company's
  filings actually got cited across real answers is genuine, queryable
  data the existing schema already supports without one. Flagged here as
  a deliberate scope pivot, not silently swapped in.
- The 7-day query-volume series is always zero-filled to exactly 7 points
  (oldest first), even on days with no activity -- computed in Python
  from a `dict` keyed by date, not left to SQL's `GROUP BY` (which only
  ever returns days that actually have rows), so the chart never renders
  a gap.
- `low_confidence_rate` is `None`, not `0.0`, when `total_queries == 0` --
  "no data yet" and "a real 0% flagged rate" are different facts the KPI
  card needs to be able to tell apart, the same nullable-vs-zero
  discipline `average_confidence_score` already used since Phase 3.
- `func.count(func.distinct(case((flagged_expr, Answer.answer_id))))` is
  the standard SQL trick for "count distinct rows matching a condition"
  in one aggregate pass instead of a second query -- `case()` with no
  `else_` defaults to `NULL`, and `count(DISTINCT ...)` ignores `NULL`s.
**Tradeoffs / deliberately left out:** No admin-only authorization check
-- `tenant.role` is always `None` until real auth exists (`deps.py`), so
there's nothing to check against yet; anyone can currently hit these
routes, matching every other route's Phase 3-established precedent.
`FlaggedAnswerResponse` has no "Reviewed" vs. "Pending Review" workflow
status (the original frontend mock showed one) -- no such column exists
anywhere in the ER model (`EvalResult.flagged_by_human` is a boolean
flag, not a review-workflow state), and adding one wasn't asked for by
this phase's scope; the frontend instead shows each flagged answer's real
`confidence_score` where the mock showed a fabricated status badge. Live-
verified against real Postgres data (11 real queries, 3 correctly
flagged, 3 distinct cited tickers) -- see the paired frontend entry below
for the screenshot-backed browser verification.
**How it connects to the rest of the system:** Reads the exact same
`Query`/`Answer`/`Citation`/`EvalResult` rows Phase 6's `POST /query`
pipeline writes and the same `LOW_CONFIDENCE_THRESHOLD` it scores
against -- this is a read-only reporting layer on top of Phase 6's write
path, not a parallel source of truth.

---

## [2026-08-09] Compare.tsx wired to real data
**Phase:** 7 -- remaining pages (Compare, Admin)
**What was built:** Replaced `Compare.tsx`'s hardcoded `MOCK_METRICS`
table with a real entity/metric picker calling the new
`GET /compare/metric` endpoint, plus new `compareMetric`/
`CompareMetricResponse`/`CompareMetricPeriod` additions to
[`lib/api.ts`](../frontend/src/app/lib/api.ts).
**Why this approach:** The ticker dropdown is populated from
`fetchDocuments()` (already fetched everywhere else in the app, Phase 4)
rather than a new `GET /companies` endpoint -- deriving the unique,
`status === 'completed'` tickers client-side avoids adding a route this
phase's scope didn't ask for, the same "no company-picker endpoint yet"
gap `documents.py` already documented in Phase 4. The results table
deliberately does *not* reproduce the original mock's fixed Q1-Q4 grid:
real per-document tables can have different column structures (see the
paired backend entry's tradeoffs note), so each matched period renders
its own `headers`/`values` pairs rather than being forced into a shared
four-quarter shape that would be dishonest about heterogeneous real data.
Clicking a result's source location reuses `Layout.tsx`'s existing global
citation side panel (`setActiveCitation`) instead of building a second,
Compare-specific detail view -- genuine reuse of Phase 6's citation UI,
not a look-alike.
**Key concepts a reviewer should understand:**
- Three distinct empty/error states are rendered, not collapsed into one
  "nothing to show": no fully-ingested documents at all, a ticker/metric
  search that ran but matched zero periods (a valid outcome, per the
  backend's 404-vs-empty-array distinction), and a real fetch error.
- Suggested-metric chips (`Revenue`, `Net Income`, ...) are a UI shortcut
  only -- they just populate the same free-text input, since matching is
  a substring search server-side, not a fixed enum the frontend needs to
  mirror.
**Tradeoffs / deliberately left out:** No `tsconfig.json` exists yet for
this frontend (flagged since Phase 1), so this was verified via `vite
build` (real transpilation/bundling) and a live Playwright browser run,
not `tsc --noEmit`. Live-verified against the real API and real ACME
data: selecting ticker `ACME`, metric `"Data Center"` correctly rendered
the real `120.4 / 138.2 / 155.9 / 171.3` quarterly values and a working
`p.3 (table 0)` source link that opens the citation panel with the
correct document/page and the matched row highlighted -- screenshots
confirm both the results table and the citation panel; zero browser
console errors.
**How it connects to the rest of the system:** Calls the Compare backend
entry above; reuses `fetchDocuments` (Phase 4) and `Layout.tsx`'s
citation panel (Phase 6) rather than introducing parallel versions of
either.

---

## [2026-08-09] Admin.tsx wired to real data
**Phase:** 7 -- remaining pages (Compare, Admin)
**What was built:** Replaced `Admin.tsx`'s `MOCK_CHART_DATA`,
`FLAGGED_QUERIES`, and the inline "Top Query Topics" array with real
calls to `GET /admin/analytics` and `GET /admin/flagged-answers`, plus
new `fetchAdminAnalytics`/`fetchFlaggedAnswers` additions to `lib/api.ts`.
**Why this approach:** Both calls run via `Promise.allSettled`, not
`Promise.all` -- analytics and the flagged-answers table are independent
panels on the same page, so one endpoint failing (e.g. a transient DB
hiccup) shouldn't blank out the other; each panel renders its own error
state independently instead of the whole page failing together. The KPI
label "Total Queries (7d)" from the original mock was changed to "Total
Queries" (all-time) -- the backend's `total_queries` is an all-time
counter (the *volume chart* is what's actually 7-day-windowed), and
relabeling the KPI to match what it actually counts was judged better
than adding a second, redundant "queries in the last 7 days" aggregate
just to preserve the mock's exact wording.
**Key concepts a reviewer should understand:**
- Chart x-axis dates are formatted client-side from the backend's plain
  ISO `date` strings (`"2026-08-09"` -> `"Aug 9"`) via `Date.UTC(...)`
  with an explicit `timeZone: 'UTC'` in `toLocaleDateString` -- avoids
  the classic bug where parsing a bare date string with the browser's
  local timezone can silently roll the date back or forward a day.
- The flagged-answers table's "Status" column (originally a fabricated
  Pending-Review/Reviewed mock badge) was replaced with the row's real
  `confidence_score` -- see the paired backend entry's tradeoffs note for
  why no real "reviewed" state exists to show instead.
**Tradeoffs / deliberately left out:** Same `vite build` +
Playwright-live-run verification precedent as Compare.tsx (no
`tsconfig.json` yet). Live-verified against the real API: KPI cards
showed real counts (11 total queries, 27.3% low-confidence rate, 1 active
analyst, 8/9 indexed documents), the volume chart rendered a real 7-day
series with today's real spike, "Most-Cited Companies" showed real
per-ticker citation counts (ACME 13, CORP 9, AI 1), and the flagged-
answers table showed 3 real flagged rows with their real flag reasons and
confidence percentages -- screenshot-backed, zero browser console errors.
**How it connects to the rest of the system:** Calls the Admin backend
entry above; this is the last of the two pages `PROJECT_HANDBOOK.md`
Phase 7 named, and (`MOCK_PROJECTS` in `Layout.tsx` aside -- see
`docs/progress.md`'s Known Issues for why that one's out of scope) the
last mock-data source in `frontend/src/app`.

---

## [2026-08-18] `services/api/tests/eval/eval_dataset.jsonl` -- the gold Q&A set
**Phase:** 8 -- eval + observability
**What was built:** A 12-item gold Q&A set (`services/api/tests/eval/
eval_dataset.jsonl`, one JSON object per line) covering both real
ingested documents Phase 5/6/7 already established: Acme Robotics'
synthetic 10-K (ticker `ACME`, a real extracted segment-revenue table)
and Energy Services of America's real downloaded 10-K (ticker `ESOA`,
narrative-only -- no extracted tables, a documented pre-existing gap).
**Why this approach:** Every ground-truth figure and fact was pulled by
directly reading the two source PDFs in `data/uploads/` (gitignored, not
previously read end-to-end in this project's own docs), not guessed or
reconstructed from prior phases' decisions-log mentions of "the segment
table" -- the whole point of a gold set is that its answers are
independently verifiable against the real source, the same standard
`numeric_verifier.py` holds the live pipeline to. Four numeric items
against ACME's real table (a single-cell lookup, a different segment/
quarter cell, the table's own Total row, and a multi-quarter trend
requiring several cited figures in one answer -- deliberately escalating
difficulty, not four near-duplicates), two ACME narrative items (business
description, a named risk factor), three numeric items against ESOA's
*narrative* prose (revenue, net income, backlog -- each a real dollar
figure stated in running MD&A text, never a table cell), two ESOA
narrative items (its three segment names, its ticker/exchange), and one
deliberate negative control (a question about a company -- Tesla -- never
ingested at all, where the *only* correct answer is an honest decline,
zero citations).
**Key concepts a reviewer should understand:**
- The ESOA numeric items exist specifically because ESOA has **zero**
  extracted `TABLE` chunks (`docs/DECISIONS_LOG.md`'s Phase 7 Compare
  entry already flagged this as a live `layout_segmenter.py`/`camelot`
  gap) -- every ESOA numeric ground truth is a figure `numeric_verifier.
  py` must therefore verify against a `TEXT` chunk's `content` (via
  `_source_text`'s table-less branch), the opposite code path from every
  ACME numeric item. One gold set now exercises both branches of that
  function, not just the table branch Phase 6 originally live-tested.
- `expected_ticker` (matched against `CitationResponse.ticker`), not a
  guessed `document_title` substring -- the exact strings typed into
  `Document.title` at upload time were never recorded anywhere this
  dataset's author could read back (both documents were ingested via
  manual live testing, not `scripts/seed_dev_data.py`), while
  `Company.ticker` is a value this entry can state with certainty
  (`ACME`/`ESOA`, confirmed straight from the source PDFs' own cover
  pages). Building a hit-rate check on a fact nobody can verify would be
  worse than not checking it at all.
- eval-012's negative control is graded with "any expected keyword
  present," every other item with "all expected keywords present" -- a
  correct decline-to-answer can be honestly worded several different ways
  ("I couldn't find...", "not enough information...", "I'm unable to
  answer..."), but a correct factual answer must state every part of the
  fact asked for, not just one of several acceptable phrasings of it. See
  `eval/ragas_runner.py`'s `_keyword_check`.
**Tradeoffs / deliberately left out:** 12 items is small for a "gold
set" by industry standards (RAGAS/DeepEval demos often use 50-100+) --
deliberately sized to the two real documents this dev environment
actually has fully ingested, per `CLAUDE.md` §1's traceability principle:
a ground-truth answer this entry can't personally verify against the
real source isn't worth adding just to inflate the count. `docs/
progress.md`'s carried-over "ingest a second real quarterly filing"
note is exactly what unlocks a larger, still-fully-verifiable set later.
No conversational/follow-up items (`history_manager.reformulate_followup`
untested by this set) -- every item is a single fresh `/query` call;
follow-up-specific eval is a reasonable next addition, not in this pass's
scope.
**How it connects to the rest of the system:** Read entirely by
`eval/ragas_runner.py`'s `load_dataset()`; nothing else in the codebase
depends on this file's shape.

---

## [2026-08-18] `eval/ragas_runner.py` -- the eval harness
**Phase:** 8 -- eval + observability
**What was built:** `eval/ragas_runner.py` runs every gold item in
`eval_dataset.jsonl` through the **real, live** query pipeline over HTTP
(`POST /api/v1/query` against a running `uvicorn`), scores each response
two ways -- RAGAS's LLM-judged `faithfulness`/`context_precision` when
`OPENAI_API_KEY` and the `ragas`/`langchain-openai` packages are
available, a deterministic ticker-match/`confidence_score` fallback when
they aren't -- writes one `EvalResult` row per scored `Query`, prints a
summary, and exits non-zero when `--fail-under` isn't met (the CI gate's
hook).
**Why this approach:** HTTP, not a direct Python import of `core/`
pipeline internals or `api/v1/routes/query.py`'s `_handle_query` -- `eval/`
sits outside `services/api/` in `PROJECT_HANDBOOK.md` §4's repo map
specifically because it's meant to be an external consumer of the
deployed system, the same relationship a real analyst's browser has to
this API. Hitting the real endpoint exercises FastAPI's request
validation, the full middleware stack, and response serialization exactly
as a real request would -- a direct import would only ever test a
partial pipeline reachable through this one script's own import path,
which is a materially weaker guarantee for a project whose whole
differentiator is "prove it actually works end to end," not "prove the
internals type-check."

The two-mode scoring exists because a real "X% retrieval precision, Y%
groundedness" resume number (`CLAUDE.md` §8's target) has to come from an
independent LLM judge to mean anything -- but requiring `OPENAI_API_KEY`
unconditionally would mean this project's own eval gate goes fully dark
whenever that key is absent (a fresh clone, a CI run without secrets
configured, a rate-limited key), which is a worse failure mode than a
clearly-labeled fallback. The fallback isn't invented from nothing: 
`deterministic_groundedness` reuses `confidence_scorer.score_final`'s own
output (already Phase 6's real "is this grounded" signal -- numeric
verification can only ever lower it), and `citation_hit_rate` reuses the
gold set's own `expected_ticker` field -- same "no meaningful X without a
key, but never a hard failure" contract `reranker.py`/`answer_generator.
py` already established for their own optional-provider calls, applied
here to evaluation itself instead of retrieval/generation.
**Key concepts a reviewer should understand:**
- `_try_ragas_scores` is wrapped in three separate `try/except` layers
  (import, `Dataset.from_dict`/`ragas_evaluate`, per-row NaN handling) and
  never raises -- a RAGAS version-API mismatch (a real, recurring risk
  with a fast-moving library) degrades this run to the deterministic
  fallback with a printed reason, not a crashed eval run. Verified this
  phase against a real `pip install`: `ragas==0.4.3` resolved (see
  `services/api/requirements.txt`), a materially newer major version than
  the `>=0.2` floor pinned there, confirming the defensive wrapping isn't
  theoretical.
- `EvalResult` rows are upserted on `query_id` (its schema's own
  `unique=True` constraint) so re-running this script against the same
  dataset doesn't grow duplicate rows -- the same idempotency concern
  `scripts/seed_dev_data.py` solved for `Document` rows in Phase 4,
  applied here. This is also what makes `admin.py`'s
  `_flagged_condition()` `EvalResult.flagged_by_human` branch (written in
  Phase 7, `docs/progress.md` noted as present-but-dormant ever since)
  finally exercised by a real row for the first time.
- Deliberately no `conversation_id`/follow-up reformulation path exercised
  -- every gold item is a fresh `submit_query` call, matching
  `eval_dataset.jsonl`'s own scope decision (see that entry's tradeoffs).
**Tradeoffs / deliberately left out:** **Live-verified this phase, not
just statically reviewed** -- Docker Desktop had to be started fresh (it
wasn't running at the start of this session), `pip install`'s `ragas`
dependency tree took a real background wait, and the live run itself
surfaced two genuine bugs the static review above missed entirely, both
now fixed:
1. **A real RAGAS/langchain-community incompatibility.** The first live
   run correctly fell back to deterministic scoring, exactly as designed
   -- but the *reason* turned out to be worth fixing, not just tolerating:
   `ragas==0.4.3`'s own `ragas/llms/base.py` unconditionally imports
   `langchain_community.chat_models.vertexai` at module load time, a
   submodule removed from `langchain-community`'s current (0.4.x) release
   as part of that package's own "being sunset" migration. Pinning
   `langchain-community==0.3.31` (the last release with that submodule
   intact, plus its own now-unlisted `dataclasses-json` dependency --
   both added to `requirements.txt` with the full story) made the real
   RAGAS path importable; re-running produced genuine LLM-judged scores
   (`faithfulness`/`context_precision`), materially different from and
   *lower* than the deterministic fallback's numbers (mean groundedness
   0.549 vs. 0.861, mean precision 0.667 vs. 0.833 on the same 12-item
   run) -- exactly the "a more independent judge is stricter" outcome
   this two-mode design was built to eventually surface, not a
   coincidence.
2. **A real data-quality bug in the dev Postgres**, unrelated to this
   phase's own code: the `Company` row backing Energy Services of
   America's ingested 10-K had `ticker='CORP'`/`name='CORP'` -- a
   mistyped placeholder from manual upload testing in an earlier phase,
   not the real `ESOA` ticker `eval_dataset.jsonl`'s five ESOA items
   depend on. Confirmed against the source PDF's own cover page (Item 5:
   "traded on the Nasdaq Capital Market under the symbol 'ESOA'") and
   corrected with a single `UPDATE companies SET ticker='ESOA', name=
   'Energy Services of America Corporation' WHERE ...` -- a data fix, not
   a schema change, so outside `CLAUDE.md` §4's "ask before touching a
   migrated schema" boundary; flagged here rather than done silently
   since it changes what a live query against that row returns. (A
   second, separate pre-existing oddity -- a `Company` row with
   `ticker='AI'` backing an unrelated health-NLP PDF misclassified as
   `FORM_10K`, first mentioned in Phase 7's admin-analytics entry -- was
   left untouched: it's not referenced by this gold set, and fixing it
   would mean altering data Phase 7's own live-verification screenshots
   already reference.)

With both fixed, a real end-to-end run (`python eval\ragas_runner.py`
against a real `uvicorn` and the real ACME/ESOA corpus) produced: 12/12
items scored, 0 errored, RAGAS-scored mean `retrieval_precision=0.667`,
mean `groundedness_score=0.549`, keyword-check pass rate 10/12. The two
keyword-check failures (`eval-007`: ESOA total revenue; `eval-011`: ESOA
ticker/exchange) are genuine retrieval misses, not harness bugs --
confirmed by hand via `curl`: both real live answers are honest "the
context does not provide..." declines with zero citations, meaning
retrieval didn't surface the right chunk for those two specific
phrasings against ESOA's real, table-less, agentically-chunked 284-chunk
document. This is the eval harness doing exactly its job on its very
first real run: producing a specific, actionable retrieval-quality
finding (not a vague "seems fine") on real data, per `CLAUDE.md` §1's eval
mandate -- left as a real, open finding for Sam rather than papered over,
since chasing it further (retrieval-parameter tuning) is explicitly
Phase 8's *next* step, not this pass's. `--fail-under` was also
live-confirmed to actually gate: `--fail-under 0.9` against these same
real scores exits non-zero with an explicit reason printed, `--fail-under
0` (the default) doesn't.
**How it connects to the rest of the system:** Reads `eval_dataset.jsonl`;
calls the real `POST /api/v1/query` route (`api/v1/routes/query.py`,
unchanged); writes `EvalResult` rows via `src.infra.db.SessionLocal`, the
same session factory every other write path in this codebase uses;
imports `observability/metrics.py`'s `citation_hit_rate`/
`deterministic_groundedness` rather than redefining either metric.

---

## [2026-08-18] `services/api/src/observability/{tracing,metrics}.py` -- LangSmith tracing + latency/hit-rate/groundedness metrics
**Phase:** 8 -- eval + observability
**What was built:** `observability/tracing.py`'s `traced_stage()`
decorator, applied directly onto eight real `core/` pipeline functions
(`multi_query.expand_query`, `hybrid_retriever.retrieve`, `reranker.
rerank`, `answer_generator.generate_answer`, `numeric_verifier.
verify_answer`, `confidence_scorer.{retrieval_confidence,score_final}`,
`citation_resolver.resolve_source_location`, `history_manager.
reformulate_followup`) -- every real `POST /query`/`POST /query/followup`
request is traced stage-by-stage in LangSmith once `LANGCHAIN_API_KEY` is
set, not left present-but-dormant in `tracing.py` alone.
`observability/metrics.py`'s `StageTimer` is wired into `api/v1/routes/
query.py`'s `_handle_query`, timing `multi_query`/`retrieval`/`rerank`/
`generation`/`numeric_verification` and logging one structured summary
line per real request.
**Why this approach:** `traced_stage()` returns the wrapped function
**completely unwrapped** (not a thin pass-through) when tracing isn't
configured -- checked once, at decoration time, not per call. This
matters more here than for `reranker.py`/`answer_generator.py`'s
optional-provider calls: those change *what the pipeline does* when
unset (skip a quality refinement, use an extractive fallback); tracing
must never change *how* the pipeline behaves at all, only whether a
side-channel trace gets emitted elsewhere -- "disabled" has to mean
byte-identical code path, not "a thinner wrapper still runs, just doing
less." `StageTimer`, by contrast, needs no env var to degrade gracefully:
`time.perf_counter()` calls have no external dependency to fail, so it's
always-on and unconditional, the always-available floor under LangSmith's
richer (but optional) per-stage view.

Applying the decorator to eight existing files (one import + one
decorator line each, no logic touched) is a small, mechanical,
behavior-preserving change per file -- chosen over a single wrapper
around `_handle_query` as a whole because a single top-level trace would
show "the query took 2.3s" without showing *which* stage inside it did,
which is the entire diagnostic value `PROJECT_HANDBOOK.md` §6 names
tracing for ("needed to debug *why* a specific answer went wrong, not
just *that* it did" -- `docs/architecture.md`'s own framing, quoted in
this repo's tech-stack table).
**Key concepts a reviewer should understand:**
- `run_type` (`"llm"` for the three OpenAI-backed stages, `"retriever"`
  for `hybrid_retriever.retrieve`, `"chain"` default elsewhere) is
  LangSmith's own vocabulary, not an Aegis-specific label -- it's what
  makes LangSmith's UI render token counts on the `"llm"`-typed spans
  correctly.
- `StageTimer.log_summary()` logs `query_id`/`confidence_score`/
  `citation_count` alongside every stage's duration in one line, through
  the same stdlib `logging` module every other module in this codebase
  already uses -- no new dependency, and a slow or low-confidence request
  is greppable in logs without a separate metrics backend (none is in the
  agreed stack, `CLAUDE.md` §3).
- `deterministic_groundedness` (in `metrics.py`, consumed by `eval/
  ragas_runner.py`) is documented as directly reusing `confidence_scorer.
  score_final`'s own output rather than inventing a second, independently
  -drifting groundedness formula -- see that entry for the full reasoning.
**Tradeoffs / deliberately left out:** `StageTimer` **was** live-verified
this phase -- `eval/ragas_runner.py`'s real run against a real `uvicorn`
(see that entry) sent every one of the gold set's 12 questions through
`_handle_query` for real, each one logging a real `query_metrics ...
stages={...}` line with real per-stage millisecond timings, confirming
`StageTimer`'s wiring into `query.py` and `TRACING_ENABLED`'s
no-op-when-unset path both actually execute in a real request, not just
type-check. What's still **not** verified live is a real LangSmith
trace specifically: no `LANGCHAIN_API_KEY` was supplied to this session
at all (Sam confirmed having one; it goes in his local `.env`, never
shared with or typed into this session, per `.env.example`'s own "real
values, never committed" rule), so `TRACING_ENABLED` was `False` for
every real request this phase's live run made -- `traced_stage()`'s
disabled/unwrapped path is what actually ran, confirmed indirectly by
every request completing with identical behavior to Phase 6/7's own
runs, but the *enabled* path (a real trace landing in the LangSmith UI)
remains Sam's own Definition-of-Done check to perform once a real key is
in his `.env`. No metrics backend/dashboard reads `StageTimer`'s output
yet -- it's a structured log line today, the natural next step if a real
time-series need shows up later (out of scope for what Phase 8 asked
for).
**How it connects to the rest of the system:** `tracing.py` is imported
by eight `core/` modules; `metrics.py` is imported by both `api/v1/
routes/query.py` (live, per-request) and `eval/ragas_runner.py` (offline,
per gold item) -- one implementation of each metric, not two.

---

## [2026-08-18] `.github/workflows/eval-regression.yml` -- the CI eval-regression gate
**Phase:** 8 -- eval + observability
**What was built:** A scheduled (daily) + manually-dispatchable GitHub
Actions workflow that provisions Postgres/Qdrant/Redis, runs Alembic
migrations, starts a real `uvicorn` instance, runs `eval/ragas_runner.py`
against it, and fails the job if `--fail-under` isn't met.
**Why this approach:** Matches `PROJECT_HANDBOOK.md` §6 Phase 8's literal
ask ("running the eval suite on a schedule and failing the job if scores
drop below a defined threshold") using GitHub Actions' own `services:`
containers for infra, the same three services `docker-compose.yml`
already defines locally -- no new CI-only infra pattern invented.
`workflow_dispatch` inputs (`eval-api-url`, `fail-under`) exist
specifically so Sam can point a manual run at a real, already-ingested
environment (a self-hosted runner on his own machine, or a future staging
deployment) once one exists, without editing the workflow file itself.
**Key concepts a reviewer should understand:**
- **Honestly flagged, not silently glossed over:** the scheduled/default
  path provisions a *brand-new, empty* Postgres+Qdrant per run --
  GitHub-hosted `services:` containers have no state from a prior run,
  and this workflow does **not** re-ingest Acme Robotics'/Energy Services
  of America's real fixture PDFs into that empty database (both currently
  live only in the gitignored, never-committed `data/uploads/` on Sam's
  machine). Building that ingestion-in-CI path for real -- committing
  fixture PDFs, writing a synchronous (non-Celery-worker) seeding script
  that calls `ingest_document()` directly rather than via `.delay()`,
  wiring `COHERE_API_KEY`/`OPENAI_API_KEY` GitHub secrets -- is real,
  scoped Phase 9 (Deployment/CI) work, not something to bolt on silently
  inside a Phase 8 pass named for the eval *harness*, not CI
  infrastructure. Flagged explicitly in the workflow file's own header
  comment, not just here.
- Because of the above, the default ephemeral run is left in report-only
  mode (`fail-under` input default `"0"`) -- it will legitimately score
  every non-negative-control gold item near 0 (nothing to retrieve from a
  corpus that was never ingested) and the one negative-control item near
  1 (correctly finds nothing), so gating on that number today would fail
  every scheduled run for a reason that has nothing to do with a real
  regression. The gate only becomes meaningful once `eval-api-url`/
  `EVAL_API_URL` points at an environment with the real corpus ingested.
**Tradeoffs / deliberately left out:** Not run in real GitHub Actions
this phase -- doing so requires a `git push` to a branch/PR and, for the
`--fail-under`-gated path to mean anything, either `COHERE_API_KEY`/
`OPENAI_API_KEY` repository secrets or a self-hosted-runner target
neither of which this session can configure or observe the result of.
This is a real, current limitation, not a "should work" claim dressed up
as verified -- see this file's own header comment and `eval/
ragas_runner.py`'s decisions-log entry for the same caveat applied to the
harness itself.
**How it connects to the rest of the system:** Runs `eval/ragas_runner.py`
against `services/api/src/main.py`'s real app; the natural target for
Phase 9's `ci.yml`/`cd-staging.yml` to eventually run alongside, and for
the fixture-seeding follow-up noted above to complete.

---

## [2026-08-18] `services/api/Dockerfile` + `services/ingestion/Dockerfile` -- multi-stage production images
**Phase:** 9 -- deployment
**What was built:** Two multi-stage Dockerfiles. Both have a `builder`
stage that installs each service's `requirements.txt` (including
`packages/shared`'s editable local dependency) into built wheels, and a
slim `runtime` stage that only installs those wheels plus the service's
own `src/` -- no compiler, no pip build cache, no `packages/shared` source
tree in the final image. `services/api/Dockerfile` runs `uvicorn`;
`services/ingestion/Dockerfile` runs the Celery worker and additionally
installs Ghostscript + `libgl1`/`libglib2.0-0` at the OS level (camelot's
real runtime dependencies, not just a build-time one).
**Why this approach:** `pip wheel -r requirements.txt` (run from each
service's own directory, mirroring `PROJECT_HANDBOOK.md` §5.3's exact
local `cd services\api && pip install -r requirements.txt` working
directory) turns `packages/shared`'s `-e ../../packages/shared` line into
a real built wheel instead of an editable `.pth` link -- the runtime stage
never needs `packages/shared`'s source directory to exist inside it at
all, which is what actually makes a clean multi-stage split possible here
without hand-rolling a workaround for the editable install. Multi-stage
(not a single `pip install` stage) was the point of the phase's own ask --
a compiler and pip's build cache have no reason to ship in a container
that only ever runs `uvicorn`/`celery worker`.
**Key concepts a reviewer should understand:**
- **Build context is the repo root, not each service's own directory** --
  both Dockerfiles need `packages/shared` visible alongside
  `services/api`/`services/ingestion` in the build context, and the two
  are only siblings from the repo root (`docker build -f
  services/api/Dockerfile .`, not `... -f Dockerfile .` from inside
  `services/api/`). Documented at the top of both files specifically
  because it's the one thing most likely to trip someone up copying the
  "obvious" `cd services/api && docker build .` command.
- **`services/api/Dockerfile` reproduces `alembic.ini`'s own relative path
  assumption inside the image** (`COPY services/api/... ./services/api/...`,
  `COPY migrations ./migrations`) rather than flattening the layout --
  `script_location = %(here)s/../../migrations` in
  `services/api/alembic.ini` is two directories up from wherever
  `alembic.ini` itself lives, so the image keeps the same two-level
  relationship instead of needing a Docker-only `alembic.ini` override.
- **`HEALTHCHECK` hits `/health/ready`, not bare `/health`** -- the real
  readiness probe (`src/api/v1/routes/health.py`) that actually runs a
  `SELECT 1` against Postgres, matching the same endpoint
  `infra/terraform/main.tf`'s ALB target group health check hits, so
  there's one definition of "this container is healthy," not two that
  could silently disagree.
- **`services/ingestion/Dockerfile` deliberately drops `--pool=solo`** --
  that flag exists purely to work around native Windows's lack of
  `os.fork()` (`services/ingestion/src/infra/celery_app.py`'s own
  docstring, `CLAUDE.md` §8). The container runs Linux, where the default
  `prefork` pool is strictly better; keeping `--pool=solo` here would have
  silently thrown away real concurrency for a Windows-only reason that no
  longer applies.
**Tradeoffs / deliberately left out:** No non-root user complexity beyond
a single `appuser` (`useradd --uid 1000`) -- good enough to avoid running
as root, not a full read-only-root-filesystem/dropped-capabilities
hardening pass, which is out of scope for a portfolio deployment. Both
images were built locally this phase (`docker build -f
services/api/Dockerfile .` and the ingestion equivalent, from the repo
root, against the already-running Docker Desktop) as a real smoke test of
the Dockerfile syntax and dependency resolution -- see
`docs/progress.md` for the actual build outcome, since a background build
running at the time this entry was written is not something to claim
success for in advance.
**How it connects to the rest of the system:** `docker-compose.prod.yml`
builds both images from these two files; `.github/workflows/cd-staging.yml`
builds and pushes the same two Dockerfiles to ECR; `infra/terraform/main.tf`'s
two `aws_ecs_task_definition` resources run the resulting images.

---

## [2026-08-18] `docker-compose.prod.yml` + `.env.prod.example` -- production-shaped local compose file
**Phase:** 9 -- deployment
**What was built:** A second compose file, alongside the existing
(local-dev-only) `docker-compose.yml`, defining just the two services this
repo builds images for (`api`, `ingestion-worker`) and pointing them at
externally-managed Postgres/Qdrant/Redis via env vars rather than local
containers -- no bind mounts, `restart: unless-stopped` on both.
`.env.prod.example` documents the variables it expects, in both their
"real managed endpoint" and "local smoke test via `host.docker.internal`"
shapes.
**Why this approach:** `PROJECT_HANDBOOK.md` §7's "Managed services
checklist" and `docs/architecture.md` §4 both name Qdrant Cloud/RDS/managed
Redis explicitly for production -- reusing `docker-compose.yml`'s local
`postgres`/`qdrant`/`redis` service blocks here would misrepresent what
actually runs in production and defeat the point of a *prod-shaped* compose
file. Keeping it a separate file (not profiles/overrides on the existing
one) also means `docker-compose.yml`'s own "local infra only, services/api
and services/ingestion aren't containerized here" header comment stays
true without a rewrite.
**Key concepts a reviewer should understand:**
- No bind mounts is deliberate, not an oversight: the entire point of a
  multi-stage Dockerfile is that the built image *is* the deployable
  artifact -- mounting local source back over it would mean testing
  something other than what actually gets pushed to ECR.
- `env_file: .env.prod` (gitignored, matching the existing repo-root
  `.env` convention) is a real-runtime necessity for the local smoke test
  this file supports; a real staging/prod deploy never reads this file at
  all -- `infra/terraform/main.tf`'s ECS task definitions inject the same
  variables via SSM `secrets`/plain `environment`, and
  `.github/workflows/cd-staging.yml` never touches `.env.prod`. Documented
  explicitly in `.env.prod.example`'s own header so the two paths (local
  compose smoke test vs. real ECS deploy) aren't conflated.
- **A real, small bug this file's own name caused, found and fixed live
  this phase:** `.gitignore`'s existing `.env.*` / `!.env.example` pair
  (line 20-23) only excepts the one literal filename `.env.example` --
  `.env.prod.example` matched the blanket `.env.*` pattern and was
  silently gitignored despite being a placeholders-only, safe-to-commit
  file by the same convention `.env.example` itself follows. Caught by
  running `git status`/`git check-ignore -v .env.prod.example` after
  writing it, not assumed correct because the file existed on disk.
  Fixed with one added `!.env.prod.example` exception line, not a rename
  -- `.env.prod.example` is the name that actually matches this repo's
  own `<name>.example` convention for a `.env.prod` counterpart.
**Tradeoffs / deliberately left out:** **Honest limitation, flagged
explicitly (same pattern as `.github/workflows/eval-regression.yml`):**
`docker compose -f docker-compose.prod.yml up` builds and starts both
containers as a real test of the images themselves, but neither will
report healthy without real values in `.env.prod` -- this session has no
provisioned Qdrant Cloud cluster or RDS instance to point at (no AWS
credentials, `infra/terraform` never applied), so the managed-endpoint
path is written but not live-verified. The `host.docker.internal`
local-smoke-test path (pointing at this repo's own already-running
`docker-compose.yml` containers) is real infra that does exist locally
this phase -- see `docs/progress.md` for which path was actually run and
what it showed.
**How it connects to the rest of the system:** Builds
`services/api/Dockerfile` and `services/ingestion/Dockerfile`; the local
equivalent of what `infra/terraform/main.tf`'s ECS services run in a real
deployment.

---

## [2026-08-18] `infra/terraform/{main.tf,variables.tf}` -- managed Qdrant/RDS/compute scaffold
**Phase:** 9 -- deployment
**What was built:** A Terraform scaffold provisioning RDS Postgres,
ElastiCache Redis, two ECR repositories, an ECS (Fargate) cluster running
`api` (behind an ALB, health-checked against `/health/ready`) and
`ingestion-worker` (no public endpoint) as two independently-scaled
services, IAM for task execution, and SSM Parameter Store `SecureString`
params for the four secrets (`db_password`, `qdrant_cloud_api_key`,
`cohere_api_key`, `openai_api_key`) rather than plaintext task-definition
env vars.
**Why this approach:** AWS was picked as the concrete target (RDS,
ElastiCache, ECS/Fargate, ALB, ECR) because `docs/architecture.md` §4's
production diagram already names "ECS/Cloud Run" and "RDS/Cloud SQL" as
the pair of realistic options and a scaffold has to pick one concretely to
be buildable HCL rather than pseudo-code -- ECS/Fargate was chosen over
Cloud Run because it pairs directly with RDS+ElastiCache+ALB in one
provider (`aws`) instead of splitting the stack across two clouds for a
portfolio-scoped example. SSM `SecureString` over plaintext `environment`
entries on the task definition is a real, deliberate hardening choice, not
scaffold theater -- plaintext task-definition env vars are visible to
anyone with read access to the task definition itself in the AWS
console/API, which is a meaningfully worse default than a KMS-encrypted
parameter resolved only at task-start time, and costs one extra IAM policy
(`aws_iam_role_policy.ecs_read_ssm_secrets`) to wire up correctly.
**Key concepts a reviewer should understand:**
- **Qdrant Cloud is *not* provisioned by this file** -- there is no
  official Terraform provider for it as of this writing, so its
  cluster is created manually through the Qdrant Cloud console
  (`PROJECT_HANDBOOK.md` §7) and this scaffold only *consumes*
  `var.qdrant_cloud_url`/`var.qdrant_cloud_api_key`, passing them through
  to both ECS task definitions' `environment`/`secrets` blocks. Flagged in
  `variables.tf`'s own comment rather than faked with a resource block
  that would silently do nothing.
- **Default VPC / public subnets, not a dedicated VPC** -- a deliberate
  scope simplification for portfolio scale, flagged explicitly in
  `variables.tf`'s header comment: a real production deployment should put
  RDS/ElastiCache in private subnets with no public IP and route ECS
  egress through a NAT gateway instead of `assign_public_ip = true`.
- **`aws_lb_target_group.api`'s health check path (`/health/ready`) is the
  same endpoint `services/api/Dockerfile`'s own `HEALTHCHECK` hits** -- one
  definition of "healthy," reused rather than duplicated with different
  logic in two places that could drift.
- **`container_image_tag` defaults to `"staging-latest"`, not `"latest"`**
  -- matches the mutable tag `.github/workflows/cd-staging.yml` pushes on
  every merge to `main` and then triggers via
  `aws ecs update-service --force-new-deployment`; the commit-SHA tag the
  same workflow also pushes is what a real rollback (`terraform apply
  -var container_image_tag=<sha>`) targets, per `PROJECT_HANDBOOK.md` §7.
**Tradeoffs / deliberately left out:** No autoscaling policies (both
`api_desired_count`/`ingestion_desired_count` are fixed numbers, not tied
to request volume or SQS/queue-depth triggers, despite
`docs/architecture.md` §4 naming exactly that as the reason the two
services are split) -- a real next step once there's real traffic to scale
against, not something to guess thresholds for now. `skip_final_snapshot =
true` and a 1-day backup retention on the RDS instance are appropriate for
a disposable staging environment, not a real production database --
flagged inline in `main.tf` itself. **Never `terraform apply`d against a
real AWS account this phase** -- no AWS credentials were supplied to this
session (consistent with `.env.example`'s "real secrets never typed into a
session" convention). What WAS actually run, since the `terraform` CLI
isn't installed locally: the official `hashicorp/terraform` Docker image,
mounted against `infra/terraform/`, ran a real `terraform init
-backend=false` (downloaded and locked the `hashicorp/aws ~> 5.0`
provider, producing the committed `.terraform.lock.hcl`), a real
`terraform validate` (passed clean -- this catches real errors
`terraform plan`/`apply` would also catch, like a wrong attribute name or
bad block nesting, that a hand-review or a brace-balance check cannot),
and a real `terraform fmt` (found and fixed three real alignment
inconsistencies in `main.tf`). `terraform plan`/`apply` themselves were
not run -- those need real AWS credentials, which is Sam's own step per
the same convention above. This is meaningfully stronger verification
than "reviewed by hand," but still short of "known to actually
provision" -- stated precisely, not rounded up, in `docs/progress.md`.
**How it connects to the rest of the system:** `.github/workflows/cd-staging.yml`
pushes into the two ECR repos this file creates and rolls the two ECS
services it defines; both Dockerfiles are what get built into those
images.

---

## [2026-08-18] `.github/workflows/ci.yml` -- lint/type-check/test gate on every PR
**Phase:** 9 -- deployment
**What was built:** Six parallel jobs (`lint-api`, `lint-ingestion`,
`typecheck-api`, `typecheck-ingestion`, `test-api`, `test-ingestion`)
triggered on every PR into `main` and every push to `main`. `test-api`
provisions the same Postgres/Qdrant/Redis `services:` containers
`.github/workflows/eval-regression.yml` already established the pattern
for; `test-ingestion` needs none of that (its unit suite is pure-function
tests against `packages/shared`/parsing/chunking modules).
**Why this approach:** Split by service and by concern (lint vs. typecheck
vs. test) rather than one monolithic job, so a `services/ingestion`-only
PR's CI feedback doesn't wait on `services/api`'s (often slower, real-DB)
test job, and a lint failure surfaces without waiting for the full test
suite -- faster useful feedback on a PR, and failures are unambiguous
about which of the three concerns actually broke. `pytest tests -v` (not
`pytest tests/unit -v`) in both test jobs deliberately targets whatever
exists under each service's `tests/` directory, per each `pyproject.toml`'s
existing `testpaths = ["tests"]` -- the literal Phase 9 ask for
"integration tests" doesn't require a separate job or a different pytest
invocation, just a `tests/integration/` directory to eventually populate;
this workflow already picks it up the moment one exists.
**Key concepts a reviewer should understand:**
- Both lint/typecheck-ingestion jobs install Ghostscript via `apt-get`
  before `pip install -r requirements.txt` -- `camelot-py[cv]` needs it
  present (even just for a clean import in some code paths), the same
  real OS-level dependency `services/ingestion/requirements.txt`'s own
  header comment flags for local Windows dev and
  `services/ingestion/Dockerfile`'s runtime stage installs for the same
  reason.
- `eval/ragas_runner.py` is linted inside `lint-api` (not a separate job)
  because it runs inside `services/api`'s own venv and imports its `src.*`
  modules -- see that file's own Phase 8 requirements.txt comment.
**Tradeoffs / deliberately left out:** No frontend job -- `frontend/` has
no `tsconfig.json` and no test suite yet (an existing, already-flagged gap
in `docs/progress.md`'s known issues, not something newly discovered or
silently worked around here); adding a frontend CI job with nothing real
to lint/type-check/test would be scaffolding theater, not a real gate.
Real next step once `frontend/` has a lint/test setup of its own, not a
Phase 9 scope creep to invent one now.
**How it connects to the rest of the system:** Gates every PR into `main`;
`.github/workflows/cd-staging.yml` only runs after a merge, so this is the
only automated check most changes to this repo ever go through before
landing.

---

## [2026-08-18] `.github/workflows/cd-staging.yml` -- build/push/deploy on merge to main
**Phase:** 9 -- deployment
**What was built:** A two-job workflow triggered on push to `main`:
`build-and-push` builds both Dockerfiles (matrix over `api`/`ingestion`),
pushes each to its ECR repo under two tags (`${{ github.sha }}` and the
mutable `staging-latest`); `deploy-staging` then force-redeploys both ECS
services via `aws ecs update-service --force-new-deployment` and waits for
the `api` service to stabilize.
**Why this approach:** SHA + mutable-tag double-tagging directly
implements `PROJECT_HANDBOOK.md` §7's explicit rollback requirement ("tag
images with the commit SHA, not just `latest`, so a rollback is a redeploy
of a known-good SHA") while still giving `--force-new-deployment` a stable
tag (`staging-latest`) to pick up without needing a `terraform apply` on
every single merge -- a rollback specifically means re-pointing
`infra/terraform/variables.tf`'s `container_image_tag` at an old SHA and
re-applying, not re-running this workflow. OIDC-based
`aws-actions/configure-aws-credentials` (`role-to-assume`, no long-lived
`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` secrets) was chosen over
static IAM user keys as the credential path -- GitHub Actions' own
current best practice, and avoids a long-lived AWS credential sitting in
repository secrets indefinitely.
**Key concepts a reviewer should understand:**
- This workflow reads `infra/terraform/main.tf`'s own outputs
  (`ecr_api_repository_url`, `ecr_ingestion_repository_url`,
  `ecs_cluster_name`) as GitHub Actions *repository variables*
  (`vars.ECR_API_REPOSITORY`, `vars.ECR_INGESTION_REPOSITORY`,
  `vars.ECS_CLUSTER`, `vars.ECS_SERVICE_API`, `vars.ECS_SERVICE_INGESTION`)
  -- Terraform doesn't push to GitHub itself, so these are a manual
  one-time copy-paste from `terraform output` into the repo's Settings ->
  Secrets and variables -> Actions once the stack is actually applied.
  Named explicitly here so that step isn't a silent prerequisite someone
  has to reverse-engineer from a failed run.
**Tradeoffs / deliberately left out:** **Never run in real GitHub
Actions this phase**, same honest-limitation pattern as
`.github/workflows/eval-regression.yml` and `infra/terraform/main.tf`'s
own header comment -- it needs `secrets.AWS_DEPLOY_ROLE_ARN` (an IAM role
with an OIDC trust policy for this specific GitHub repo, itself not
scaffolded in `infra/terraform/main.tf` -- a real Phase-9-adjacent gap,
left for whenever this is actually deployed rather than guessed at here)
and the Terraform stack already applied for the ECR repo/ECS cluster names
it deploys into. Both are real, current gaps, not "should work" claims
dressed up as verified.
**How it connects to the rest of the system:** Consumes both Dockerfiles
and `infra/terraform/main.tf`'s ECR/ECS resources; the automated
counterpart to `docker-compose.prod.yml`'s manual local smoke test.
