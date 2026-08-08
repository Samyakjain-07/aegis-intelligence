"""Stub tenant-resolution middleware -- resolves which organization a
request belongs to.

Registered after `AuthMiddleware` in `main.py`'s execution order, since
real tenant resolution should eventually derive from the verified
identity `AuthMiddleware` produces, not a header. For now, no verified
identity exists yet, so this reads an `X-Org-Id` header directly -- purely
so `deps.get_tenant_context` has something real to read back out and the
DI wiring can be exercised end-to-end before real auth exists.
"""
from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from src.api.v1.deps import PLACEHOLDER_ORG_ID


class TenantContextMiddleware(BaseHTTPMiddleware):
    """Sets `request.state.org_id` (from `X-Org-Id` if present and a valid
    UUID, else `PLACEHOLDER_ORG_ID`) and `request.state.user_id` /
    `request.state.role` (always `None` for now -- there's no verified
    user identity to derive them from yet)."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        org_header = request.headers.get("X-Org-Id")
        org_id = PLACEHOLDER_ORG_ID
        if org_header:
            try:
                org_id = uuid.UUID(org_header)
            except ValueError:
                org_id = PLACEHOLDER_ORG_ID
        request.state.org_id = org_id
        request.state.user_id = None
        request.state.role = None
        return await call_next(request)
