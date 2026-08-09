"""Database engine and session factory for `services/ingestion`.

Deliberately the same shape as `services/api/src/infra/db.py` (same
`DATABASE_URL` env var, same sync `psycopg2` engine, same
`sessionmaker` setup) but a genuinely separate module -- the two services
are not allowed to import each other's Python code (see
`src/storage/models.py`'s docstring), so this file exists independently
even though it's nearly line-for-line identical to its API-side
counterpart. They agree by pointing at the same Postgres instance via the
same env var, never by sharing code.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

# Repo-root .env -- services/ingestion has no .env of its own, matching
# services/api's convention (docker-compose.yml / .env.example both live
# at the repo root too).
load_dotenv()

DATABASE_URL: str = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg2://changeme:changeme@localhost:5432/aegis"
)

engine: Engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine, autoflush=False, autocommit=False
)
