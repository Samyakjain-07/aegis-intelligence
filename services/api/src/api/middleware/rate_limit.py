"""Stub rate-limiting middleware -- every request passes through
uncounted.

Real per-tenant limiting (Redis-backed, keyed on the `org_id`
`TenantContextMiddleware` resolves, returning 429 + `Retry-After` per
`docs/architecture.md` §3's "Rate limit exceeded (per tenant)" failure
path) is wired in once `infra/redis_client.py` exists in a later phase.
Registered innermost of the three middleware (see `main.py`) so it would
see an already-resolved tenant before deciding whether to limit -- that
ordering doesn't need to change when the real logic is added.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """No-op today. Always calls through to the next layer."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        return await call_next(request)
