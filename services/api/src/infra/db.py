"""Database engine and session factory for `services/api`.

Deliberately minimal for Phase 2 — just enough for Alembic's `migrations/
env.py` to resolve a real connection and to apply the first migration
against the local Postgres. Request-scoped session dependency injection
(`api/v1/deps.py`), connection-pool tuning, and any decision about an
async engine alongside FastAPI's async routes are Phase 3's job, not
this one's — `requirements.txt` only pins the sync `psycopg2-binary`
driver so far, which is what a sync `Engine`/`Session` here matches.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

# Repo-root .env, matching how docker-compose.yml / .env.example are laid
# out (both live at the repo root, not inside services/api).
load_dotenv()

DATABASE_URL: str = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg2://changeme:changeme@localhost:5432/aegis"
)

engine: Engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine, autoflush=False, autocommit=False
)
