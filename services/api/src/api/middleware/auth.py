"""Stub auth middleware -- extracts a bearer token, verifies nothing yet.

Real JWT/API-key verification (rejecting missing/expired/malformed
tokens with a 401) replaces the body of `dispatch` in a later phase.
Every route already runs "behind" this middleware, registered first in
`main.py`'s execution order (see that file's comment on why), so that
swap won't touch route code or `deps.py`.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

_BEARER_PREFIX = "bearer "


class AuthMiddleware(BaseHTTPMiddleware):
    """Sets `request.state.auth_token` to the raw bearer token string, or
    `None` if the `Authorization` header is missing or isn't a bearer
    token. No signature/expiry check, no rejection -- that's the point of
    this being a stub."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        auth_header = request.headers.get("Authorization", "")
        token: str | None = None
        if auth_header.lower().startswith(_BEARER_PREFIX):
            token = auth_header[len(_BEARER_PREFIX) :].strip()
        request.state.auth_token = token
        return await call_next(request)
