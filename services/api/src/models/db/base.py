"""Declarative base and shared constraint-naming convention.

Every model in `models/db/` inherits from `Base` defined here.

Why the naming convention matters: without it, unnamed constraints (foreign
keys, unique constraints, checks) get driver-assigned names that differ
between what SQLAlchemy would pick and what Postgres would pick, and can
even differ between two autogenerate runs. `alembic revision --autogenerate`
diffs the live database's constraint names against what the models declare
-- if those names aren't deterministic, autogenerate can't reliably tell
"this constraint was renamed" from "this one was dropped and an unrelated
one was added", and produces noisy or wrong migrations. Fixing the naming
convention once, here, at the base class, means every constraint in every
model gets a predictable name for free.
"""
from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Standard SQLAlchemy-recommended convention (also what Alembic's own docs
# suggest) -- ix/uq/ck/fk/pk cover every constraint/index type Postgres
# supports that we use in this schema.
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Shared declarative base for all Aegis Intelligence ORM models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
