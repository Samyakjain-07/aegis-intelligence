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
