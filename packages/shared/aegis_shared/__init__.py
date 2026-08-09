"""aegis_shared — code shared between services/api and services/ingestion.

Deliberately tiny and dependency-free (no SQLAlchemy, no FastAPI, no
Celery): anything heavier belongs in one service or the other, not here,
since importing this package from either service must never drag in the
other service's stack. See `packages/shared/aegis_shared/source_location.py`
for the one type that currently lives here and why.
"""
from __future__ import annotations

from aegis_shared.source_location import SourceLocation

__all__ = ["SourceLocation"]
