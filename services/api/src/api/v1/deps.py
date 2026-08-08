"""FastAPI dependency injection: DB session + tenant-context stub.

Every route in `api/v1/routes/` depends on `get_db` and
`get_tenant_context` (even though no route body queries the DB or checks
the tenant yet -- see each route file) so the DI wiring itself is already
correct and exercised end-to-end. Real auth/tenant resolution logic lives
in the middleware (`api/middleware/`), not here -- this module only reads
back what the middleware already resolved onto `request.state`, into a
typed value.
"""
from __future__ import annotations

import uuid
from collections.abc import Generator
from dataclasses import dataclass

from fastapi import Request
from sqlalchemy.orm import Session

from src.infra.db import SessionLocal
from src.models.db.enums import UserRole

# Stand-in tenant for every request until real auth exists. A well-known
# nil UUID rather than `None` so tenant-scoped queries written from Phase
# 4 onward (`WHERE org_id = tenant.org_id`) never need a `None`-check
# special case; it's also unmistakable if it ever leaks into a log line or
# response, unlike a real-looking placeholder UUID would be.
PLACEHOLDER_ORG_ID: uuid.UUID = uuid.UUID(int=0)


def get_db() -> Generator[Session, None, None]:
    """Request-scoped SQLAlchemy session. Opens one `SessionLocal()` per
    request and always closes it after, including on an unhandled
    exception. No route uses it for a real query yet in this phase -- it
    exists so every route's signature is already correct for Phase 4 to
    fill in against, and so `alembic`/model changes surface here (a broken
    `SessionLocal`) rather than silently later.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@dataclass(frozen=True)
class TenantContext:
    """Resolved tenant identity for the current request. `user_id`/`role`
    are `None` until real auth exists -- `TenantContextMiddleware`
    currently only ever resolves `org_id` (from a header, see that
    module), never an actual authenticated user."""

    org_id: uuid.UUID
    user_id: uuid.UUID | None
    role: UserRole | None


def get_tenant_context(request: Request) -> TenantContext:
    """Reads whatever `TenantContextMiddleware` set on `request.state` and
    returns it as a typed `TenantContext`. Falls back to
    `PLACEHOLDER_ORG_ID`/`None`/`None` if the middleware didn't run (e.g.
    a route exercised directly in a unit test without the full middleware
    stack) so this dependency never raises just because auth isn't
    implemented yet -- a missing/invalid identity is a 401/403 concern for
    a later phase's real auth middleware, not something this stub should
    simulate by failing.
    """
    return TenantContext(
        org_id=getattr(request.state, "org_id", PLACEHOLDER_ORG_ID),
        user_id=getattr(request.state, "user_id", None),
        role=getattr(request.state, "role", None),
    )
