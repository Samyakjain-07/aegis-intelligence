"""Pydantic response schemas for the `citations` route and for
`QueryResponse.citations` (`models/schemas/query.py`).

`CitationResponse` started (Phase 3) as a field-for-field mirror of
`models.db.citation.Citation` -- see `docs/architecture.md` §7
(`ANSWER ||--o{ CITATION : cites`, `DOCUMENTCHUNK ||--o{ CITATION :
referenced_by`). Phase 6 adds display-only fields (`document_title`,
`document_type`, `ticker`, `page_number`, `fiscal_year`,
`fiscal_quarter`) sourced from the cited chunk's `Document`/`Company`,
not from `Citation` itself -- so the Chat UI's source panel (ticker, doc
type, page, date-ish fiscal period) can render without a second
round-trip per citation. Because these fields don't live on the `Citation`
row, `api/v1/routes/query.py` builds `CitationResponse` instances by hand
(from a `RetrievedChunk` + the row it just persisted) rather than via
`CitationResponse.model_validate(citation_orm)` -- `model_config =
ConfigDict(from_attributes=True)` stays set for the `citations.py` route,
which *does* read a bare `Citation` row and still wants the original
1:1-mirrored fields to validate straight off the ORM instance.
"""
from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict

from src.models.db.enums import DocumentType


class CitationResponse(BaseModel):
    """One evidence pointer, as shown to the user alongside an answer."""

    model_config = ConfigDict(from_attributes=True)

    citation_id: uuid.UUID
    answer_id: uuid.UUID
    chunk_id: uuid.UUID
    exact_location: str
    snippet: str

    # Phase 6 additions -- display context the Chat UI's citation panel
    # needs, joined once server-side instead of the frontend making a
    # second call per citation. See module docstring.
    document_title: str
    document_type: DocumentType
    ticker: str
    page_number: int
    fiscal_year: int
    fiscal_quarter: int | None
