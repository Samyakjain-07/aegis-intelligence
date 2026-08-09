"""`GET /citations/{citation_id}` -- stub handler backing
`docs/architecture.md` §8's "Expand a citation" use case.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.v1.deps import TenantContext, get_db, get_tenant_context
from src.models.db.enums import DocumentType
from src.models.schemas.citation import CitationResponse

router = APIRouter(prefix="/citations", tags=["citations"])


@router.get("/{citation_id}", response_model=CitationResponse)
def get_citation(
    citation_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
) -> CitationResponse:
    """Placeholder citation -- echoes the requested ID with empty text
    fields. A later phase looks this up via `Citation.chunk` (so the
    frontend can render the full source passage, not just the stored
    `snippet`) and 404s if the citation doesn't exist or its parent
    `Answer` isn't visible to this tenant.

    Still a stub -- out of Phase 6's scope (`query.py` is the route that
    phase wires up for real) -- but `CitationResponse` gained required
    display fields this phase (`document_title`/`document_type`/`ticker`/
    `page_number`/`fiscal_year`/`fiscal_quarter`, see that schema's
    docstring), so this placeholder construction needs matching
    placeholder values to keep type-checking/returning correctly until
    this route's real `Citation.chunk`-joined lookup is built.
    """
    return CitationResponse(
        citation_id=citation_id,
        answer_id=uuid.uuid4(),
        chunk_id=uuid.uuid4(),
        exact_location="",
        snippet="",
        document_title="",
        document_type=DocumentType.FORM_10K,
        ticker="",
        page_number=0,
        fiscal_year=0,
        fiscal_quarter=None,
    )
