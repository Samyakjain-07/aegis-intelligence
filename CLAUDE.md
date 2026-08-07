# CLAUDE.md — Operating Charter for Claude Code on Aegis Intelligence

This file governs how Claude Code behaves in this repository. Read it before
starting any task. If something requested in a session conflicts with this
file, say so and ask rather than silently picking a side.

---

## 1. What this project is

**Aegis Intelligence** is a multi-modal RAG platform over SEC filings
(10-Ks, 10-Qs, earnings call transcripts) for a portfolio targeting GenAI
Engineer / RAG Engineer / MLOps Engineer roles, 2026–2027 cycle.

The two things that make this more than a tutorial clone, and that every
design decision below exists to protect:

1. **Numeric traceability.** Every number in an answer must be verified
   against the actual source table before it's shown as confident. No
   number reaches the user ungrounded.
2. **A quantifiable eval story.** Retrieval precision and groundedness are
   measured against a gold Q&A set, in CI, on every change — not asserted
   from vibes.

Full architecture, tech stack, and the phased build plan live in
`PROJECT_HANDBOOK.md`. Read the relevant phase section there before starting
work — this file tells you *how* to work, that file tells you *what* to
build.

---

## 2. Your role has changed — read this before doing anything else

Sam does not hand-type implementation code anymore. **You write it
directly**, file by file, phase by phase, following `PROJECT_HANDBOOK.md`.
This supersedes any earlier instruction that limited you to environment
setup, scaffolding, or stub files only.

This is still explicitly a **learning-through-implementation** project, not
a delivery job. Sam needs to be able to explain every part of this system,
unprompted, to an interviewer. That changes what "done" means for a task —
done means *implemented and explained*, not just implemented.

Concretely, this means two docs you own and must keep current:

- **`docs/progress.md`** — a factual audit of what exists in the repo right
  now. Regenerate it after any phase where repo state materially changed.
  Verify by reading files; never mark something done because a folder
  exists.
- **`docs/DECISIONS_LOG.md`** — the reasoning companion to the code. See §5.
  **Append an entry after every implementation unit, before calling the
  task finished.** This is a deliverable of the task, on the same footing
  as the code itself — not optional documentation you get to if there's
  time.

---

## 3. Engineering standards (non-negotiable)

- **Full PEP 484 type annotations** on every Python function/method:
  parameter types, return type, `X | None` for optionals (project targets
  Python 3.11+, so use `|`, not `typing.Optional`), generics where they add
  real information. If a typing choice isn't obvious, say why in the
  decisions log entry.
- **SQLAlchemy 2.0 style only** — `Mapped[...]` / `mapped_column(...)`.
  Never the legacy `Column(...)` declarative style.
- **Fixed model build order**: `base.py -> enums.py -> organization.py ->
  user.py -> company.py -> document.py -> document_chunk.py -> table_data.py
  -> conversation.py -> query.py -> answer.py -> citation.py ->
  eval_result.py`. This order exists because each file's FK relationships
  depend on the ones before it. Don't reorder without flagging why.
- **Folder structure follows `PROJECT_HANDBOOK.md` §4 exactly.** If a new
  file doesn't have an obvious home in that structure, stop and ask rather
  than inventing a new convention on the spot.
- **No new dependency outside the agreed stack** (FastAPI, SQLAlchemy 2.0 +
  Alembic, PostgreSQL, Qdrant, Celery + Redis, Cohere rerank, pymupdf +
  camelot, React/TS/Vite/shadcn/Radix/Tailwind, RAGAS or DeepEval,
  LangSmith or Arize Phoenix, Docker + GitHub Actions) without flagging it
  first and stating what it replaces or adds.
- **PowerShell is the default shell.** Give PowerShell commands. Only
  mention a Unix equivalent if it differs meaningfully (it usually will for
  venv activation, `rm`, and path separators).

---

## 4. Standing boundaries — proceed vs. ask first

**Proceed without asking:** writing new files that fit the agreed
structure, scaffolding, running installs/migrations/tests, fixing bugs that
don't change a public interface, writing the decisions-log entry and
progress.md updates.

**Stop and ask first if a task would:**
- Change a database schema that's already been migrated against real data
  (a new column is usually fine; renaming/dropping an existing one isn't,
  without discussion)
- Rewrite or delete existing frontend logic wholesale rather than fixing it
  in place — the frontend is a real Figma export, not disposable
- Deviate from the ER model, the folder structure, or the nine-phase order
- Add a new external service or dependency not already in the agreed stack
- Span more than one phase's worth of work in a single pass

If you think a boundary *should* be crossed (e.g., the ER model has a real
gap), say so explicitly and explain the tradeoff — don't just do it, and
don't just silently comply if Sam asks for something that contradicts an
earlier decision either. Push back constructively, the same way you would
in a code review.

---

## 5. Required after every implementation: a `docs/DECISIONS_LOG.md` entry

Append — never overwrite — using this template, newest entry at the bottom:

```markdown
## [YYYY-MM-DD] <short title of what was built>
**Phase:** <n — phase name, e.g. "2 — DB schema">
**What was built:** <1-3 plain-language sentences>
**Why this approach:** <the actual reasoning - what alternatives existed
and why this one won, not just a restatement of what the code does>
**Key concepts a reviewer should understand:** <bullets - e.g. "why
Mapped/mapped_column over Column," "what the UniqueConstraint on
(document_id, page_number, chunk_index) buys us here">
**Tradeoffs / deliberately left out:** <bullets - what's simplified for now
and why that's an acceptable simplification at this stage>
**How it connects to the rest of the system:** <1-2 sentences - what calls
this, what this calls, what would break if it were removed>
```

Write every entry so that a technical interviewer skimming it — or Sam,
six months from now, cold — understands the *why*, not just the *what*.
This file is Sam's primary artifact for explaining the project to anyone.
Treat the quality bar accordingly: no filler, no restating the code in
prose, actual reasoning.

---

## 6. Task loop

1. Read the relevant phase section of `PROJECT_HANDBOOK.md`.
2. Check `docs/progress.md` for current state — don't assume a prior phase
   is complete because it's supposed to be.
3. Implement.
4. Run that phase's verification commands (tests / type-check / lint - see
   the phase's "Definition of Done" in `PROJECT_HANDBOOK.md`).
5. Append the `docs/DECISIONS_LOG.md` entry (§5).
6. If repo state materially changed, regenerate `docs/progress.md`.
7. Summarize what changed, in plain language, in your response to Sam -
   this is in addition to the log entry, not a replacement for it.

---

## 7. Reference docs in this repo

- `PROJECT_HANDBOOK.md` — full phased implementation plan, environment
  setup, per-phase Claude Code prompts, deployment, portfolio packaging.
- `docs/architecture.md` — system flow (both pipelines), ER diagram,
  use-case diagrams, decision/failure-path tables.
- `docs/progress.md` — current, factual state of the repo.
- `docs/DECISIONS_LOG.md` — reasoning log, append-only, this file's output.

---

## 8. Environment

- OS: Windows | Shell: PowerShell | Editor: VS Code (+ Claude Code).
- Python 3.11+, one venv per service (`services/api`, `services/ingestion`)
  — see `PROJECT_HANDBOOK.md` §5 for exact setup commands.
- Node LTS for `frontend/`.
- Local infra (Postgres, Qdrant, Redis) via `docker-compose.yml` — don't
  assume it's running; check before a task that needs it.
- Celery on native Windows has known pool-concurrency issues — local dev
  uses `--pool=solo` (see `PROJECT_HANDBOOK.md` §5 and the Phase 5 note).
