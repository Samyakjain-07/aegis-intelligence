"""Pydantic response schemas for `health.py`.

Two separate response shapes for two separate Kubernetes-style probes: a
liveness probe just answers "is the process up" (no dependency checks --
a slow Postgres shouldn't make an orchestrator kill and restart a
perfectly healthy API process), a readiness probe answers "can this
instance actually serve traffic right now" and does check its one hard
dependency at this phase, Postgres.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class LivenessResponse(BaseModel):
    """Always `"ok"` if the process can respond at all -- no dependency
    checks by design (see module docstring)."""

    status: Literal["ok"]


class ReadinessResponse(BaseModel):
    """`status` is `"degraded"` rather than a raised 5xx when the database
    check fails, so the response body stays informative -- the route
    itself sets the HTTP status code to 503 in that case; this model
    describes the body either way."""

    status: Literal["ok", "degraded"]
    database_reachable: bool
