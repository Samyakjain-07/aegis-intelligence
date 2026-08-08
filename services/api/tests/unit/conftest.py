"""Shared pytest fixtures for `services/api` unit tests.

Tests run against the real local Postgres from `docker-compose.yml`, not
SQLite -- see the docs/DECISIONS_LOG.md entry for this file for why (short
version: the models use Postgres-native `UUID`, `JSONB`, and `ENUM` column
types that SQLite doesn't faithfully emulate, and the constraint/FK
behaviors these tests exist to verify are exactly the kind of thing that
differs between database backends).

Every test gets its own outer transaction that's always rolled back, never
committed, so tests can freely insert/commit/delete/violate constraints
without leaving rows behind or needing to reset the database between runs.
"""
from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from src.infra.db import DATABASE_URL


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    """One engine for the whole test session. Safe to share across tests
    because the per-test isolation below comes from the transaction/
    savepoint fixture, not from a fresh engine/connection each time."""
    eng = create_engine(DATABASE_URL)
    yield eng
    eng.dispose()


@pytest.fixture()
def db_session(engine: Engine) -> Iterator[Session]:
    """A `Session` bound to a single connection wrapped in an outer
    transaction that this fixture always rolls back on teardown -- the
    standard SQLAlchemy 2.0 pattern for isolated, real-database-backed
    tests ("Joining a Session into an External Transaction" in
    SQLAlchemy's docs), rather than truncating tables between tests or
    rebuilding the schema per test.

    `join_transaction_mode="create_savepoint"` is what makes this safe even
    though test code below calls `session.commit()`: each `commit()` only
    releases a `SAVEPOINT` nested inside the outer transaction and
    immediately opens a new one, so nothing a test does ever reaches the
    real database outside of this fixture's own transaction.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    yield session

    session.close()
    transaction.rollback()
    connection.close()
