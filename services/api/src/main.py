"""FastAPI application entrypoint -- builds the app, registers
middleware, and registers every v1 router.

Run with (from `services/api`, venv activated):
    uvicorn src.main:app --reload
"""
from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.middleware.auth import AuthMiddleware
from src.api.middleware.rate_limit import RateLimitMiddleware
from src.api.middleware.tenant_context import TenantContextMiddleware
from src.api.v1.routes import admin, citations, conversations, documents, health, query

load_dotenv()

# Phase 4 (PROJECT_HANDBOOK.md) is the first phase where the frontend
# actually calls this API from a browser (`frontend/src/app/lib/api.ts`) --
# Vite's dev server and this API run on different origins/ports, so the
# browser enforces CORS even though `curl`/server-to-server calls never
# hit this restriction (it's purely a browser-enforced policy). Defaults
# cover Vite's own default port (5173) plus 3000 as a common alternate;
# override with a comma-separated CORS_ALLOWED_ORIGINS for anything else
# (e.g. a non-default `--port` or a deployed frontend origin).
_DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"
CORS_ALLOWED_ORIGINS: list[str] = [
    origin.strip()
    for origin in os.environ.get("CORS_ALLOWED_ORIGINS", _DEFAULT_CORS_ORIGINS).split(",")
    if origin.strip()
]


def create_app() -> FastAPI:
    """Builds and returns the FastAPI app. A factory function rather than
    a bare module-level `FastAPI()` so a later phase's tests can construct
    fresh app instances (e.g. with dependency overrides for `get_db`)
    without import-order tricks.
    """
    app = FastAPI(
        title="Aegis Intelligence API",
        description=(
            "Multi-modal RAG platform over SEC filings -- query, "
            "document, conversation, citation, and admin endpoints."
        ),
        version="0.1.0",
    )

    # Order matters and is deliberately NOT alphabetical: Starlette's
    # `add_middleware` prepends to an internal list, so the *last* call
    # here ends up *outermost* and therefore runs *first* on each incoming
    # request (full trace in docs/DECISIONS_LOG.md's Phase 3 entry).
    # Registering RateLimit -> TenantContext -> Auth, in that call order,
    # produces Auth -> TenantContext -> RateLimit -> route as the actual
    # execution order -- which is the order that's semantically correct:
    # resolve identity first, then resolve which tenant that identity
    # belongs to, then rate-limit per tenant.
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(TenantContextMiddleware)
    app.add_middleware(AuthMiddleware)
    # CORS goes outermost of all (added last), so a browser's preflight
    # `OPTIONS` request gets answered before it ever reaches Auth/
    # TenantContext/RateLimit -- those middlewares have nothing to check on
    # a preflight (no body, no real auth header yet) and shouldn't be in
    # the way of it succeeding.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health checks are unversioned and unprefixed on purpose -- load
    # balancers / container orchestrators expect a stable path that
    # doesn't move if the API's own versioning changes.
    app.include_router(health.router)

    app.include_router(query.router, prefix="/api/v1")
    app.include_router(documents.router, prefix="/api/v1")
    app.include_router(conversations.router, prefix="/api/v1")
    app.include_router(citations.router, prefix="/api/v1")
    app.include_router(admin.router, prefix="/api/v1")

    return app


app: FastAPI = create_app()
