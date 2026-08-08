"""Alembic environment script.

Lives at the repo root (`migrations/`) per `PROJECT_HANDBOOK.md` §4's
structure map, while `alembic.ini` lives in `services/api` (where the venv
and `alembic` dependency actually are) and points its `script_location`
back here. `prepend_sys_path = .` in `alembic.ini` adds the *current
working directory* (`services/api`, per the Definition of Done's
`cd services\api` first step) to `sys.path`, which is what makes
`import src.models.db` below resolve.
"""
from __future__ import annotations

import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

# Repo-root .env — this file is at <repo_root>/migrations/env.py, so one
# parent up is <repo_root>. Same DATABASE_URL contract as
# services/api/src/infra/db.py; loaded independently here since Alembic
# runs as its own process, not through that module.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# This is the Alembic Config object, which provides access to the values
# within the .ini file in use.
config = context.config

# Interpret the config file for Python logging. This line sets up loggers
# basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import every model so Base.metadata is fully populated before Alembic
# diffs it against the live database — see models/db/__init__.py's
# docstring for why importing only a subset would be a real bug here.
from src.models.db import Base

target_metadata = Base.metadata


def get_url() -> str:
    """Real DATABASE_URL from the environment wins over whatever's
    (deliberately) left as a placeholder in alembic.ini."""
    return os.environ.get(
        "DATABASE_URL", config.get_main_option("sqlalchemy.url", "")
    )


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine, though
    an Engine is acceptable here as well. By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the script
    output.
    """
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine and associate a
    connection with the context.
    """
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
