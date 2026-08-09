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
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.infra.db import SessionLocal
from src.models.db.enums import OrgTier, UserRole
from src.models.db.organization import Organization
from src.models.db.user import User

# Stand-in tenant for every request until real auth exists. A well-known
# nil UUID rather than `None` so tenant-scoped queries written from Phase
# 4 onward (`WHERE org_id = tenant.org_id`) never need a `None`-check
# special case; it's also unmistakable if it ever leaks into a log line or
# response, unlike a real-looking placeholder UUID would be.
PLACEHOLDER_ORG_ID: uuid.UUID = uuid.UUID(int=0)

# Same idea as PLACEHOLDER_ORG_ID, one level down: Phase 6 is the first
# phase that needs a real, persisted `User` row (a `Conversation.user_id`
# FK has to point at something that actually exists), but there is still
# no real auth and no seed script populates `organizations`/`users` --
# `scripts/seed_dev_data.py` (Phase 4) only ever seeded `Company`/
# `Document`. Rather than block Phase 6 on building real auth (far out of
# scope) or silently inventing a differently-shaped workaround, this
# reuses the exact find-or-create pattern `documents.py` already
# established for `Company` in Phase 4, one level up the hierarchy.
_PLACEHOLDER_ORG_NAME = "Aegis Default Org"
_PLACEHOLDER_USER_EMAIL = "dev@aegis.local"


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


def get_or_create_actor(db: Session, tenant: TenantContext) -> User:
    """Resolves the `User` row a new `Conversation` should belong to.

    `tenant.user_id` is always `None` today (`TenantContextMiddleware`
    never resolves a real one -- see its own docstring), so this always
    falls through to finding-or-creating one well-known placeholder
    `User` under one well-known placeholder `Organization`
    (`PLACEHOLDER_ORG_ID`). Both are looked up by primary key / unique
    email first so repeated requests reuse the same rows instead of
    growing a new `Organization`+`User` per query -- the same
    find-or-create shape (and the same accepted, low-probability
    concurrent-request race, not guarded with `SELECT ... FOR UPDATE`)
    `documents.py`'s `create_document` already uses for `Company`.

    Once real auth exists, this function's body is exactly what changes
    -- callers (`query.py`) don't need to, since they already only depend
    on getting back *some* real, persisted `User`.
    """
    org = db.get(Organization, tenant.org_id)
    if org is None:
        org = Organization(org_id=tenant.org_id, name=_PLACEHOLDER_ORG_NAME, tier=OrgTier.FREE)
        db.add(org)
        db.flush()

    if tenant.user_id is not None:
        existing = db.get(User, tenant.user_id)
        if existing is not None:
            return existing

    user = db.execute(
        select(User).where(User.org_id == org.org_id, User.email == _PLACEHOLDER_USER_EMAIL)
    ).scalar_one_or_none()
    if user is None:
        user = User(
            org_id=org.org_id,
            name="Dev User",
            email=_PLACEHOLDER_USER_EMAIL,
            role=UserRole.ANALYST,
        )
        db.add(user)
        db.flush()
    return user
