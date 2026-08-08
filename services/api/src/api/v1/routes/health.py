"""`GET /health`, `GET /health/ready` -- liveness/readiness probes.

Mounted without the `/api/v1` prefix (see `main.py`) -- load balancers and
container orchestrators expect a stable, unversioned health path that
doesn't move if the API's own versioning ever changes.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.api.v1.deps import get_db
from src.models.schemas.health import LivenessResponse, ReadinessResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=LivenessResponse)
def liveness() -> LivenessResponse:
    """Is the process up. No dependency checks -- see `LivenessResponse`'s
    docstring for why."""
    return LivenessResponse(status="ok")


@router.get("/ready", response_model=ReadinessResponse)
def readiness(response: Response, db: Session = Depends(get_db)) -> ReadinessResponse:
    """Can this instance actually serve traffic. Runs one cheap
    `SELECT 1` against Postgres, the API's only hard dependency as of this
    phase. Deliberately real logic, not a placeholder -- it's infra
    plumbing (a standard liveness/readiness pattern), not the RAG business
    logic `PROJECT_HANDBOOK.md` Phase 3 intentionally stubs out; an
    always-`"ok"` readiness probe would be actively misleading once this
    is deployed behind an orchestrator.
    """
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(status="degraded", database_reachable=False)
    return ReadinessResponse(status="ok", database_reachable=True)
