"""Pydantic request/response schemas for `GET/POST /documents`.

There is deliberately no request-body schema class for `POST /documents`
here (unlike the Phase 3 stub's `DocumentCreateRequest`) -- Phase 4
(`PROJECT_HANDBOOK.md`) turns it into a real `multipart/form-data` upload,
since an actual PDF's bytes have to travel in the same request as its
metadata and a JSON body can't carry binary form data. FastAPI does support
a Pydantic model as a single `Form(...)` parameter (added in 0.113), but
that was tried and reverted here: combined with a sibling `File(...)`
parameter, FastAPI treats them as two separate body parts and nests the
model's fields under its own parameter name (`{"file": ..., "form": {...}}`)
rather than flattening them alongside `file` at the top level -- not the
shape a plain HTML `<input type="file">` + `FormData()` actually sends.
The route instead declares each field as its own `Annotated[X, Form(...)]`
parameter (the standard FastAPI file-upload-plus-fields pattern), which
does flatten correctly. See `docs/DECISIONS_LOG.md`'s Phase 4 entry.

The old `DocumentCreateRequest`'s `company_id` is also gone from the write
path entirely -- the frontend has no company-picker UI (and no
`GET /companies` endpoint exists yet to back one), so the route resolves a
`Company` by ticker (find-or-create) instead.
"""
from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict

from src.models.db.enums import DocumentStatus, DocumentType


class CompanyResponse(BaseModel):
    """Nested on `DocumentResponse` so the Library page can render a
    ticker/name without a separate round-trip -- no `GET /companies`
    endpoint exists yet (out of Phase 4's scope; add it if/when the
    frontend needs to browse companies independently of their documents)."""

    model_config = ConfigDict(from_attributes=True)

    company_id: uuid.UUID
    ticker: str
    name: str
    sector: str


class DocumentResponse(BaseModel):
    """One `Document` row as returned to the client. Now includes the
    `title`/`status` columns Phase 4 added to the ORM model (the flagged
    gap from `document.py`'s Phase 2 decisions-log entry) and a nested
    `company` for display -- a genuine composition, not a strict 1:1
    mirror of `Document`, following the precedent `QueryResponse` already
    set in Phase 3 for "the read shape isn't the same as the write shape."
    """

    model_config = ConfigDict(from_attributes=True)

    document_id: uuid.UUID
    company_id: uuid.UUID
    company: CompanyResponse
    document_type: DocumentType
    fiscal_quarter: int | None
    fiscal_year: int
    upload_date: date
    source_url: str
    title: str
    status: DocumentStatus


class DocumentListResponse(BaseModel):
    """`GET /documents` response envelope. `total` currently always equals
    `len(documents)` -- there's no `limit`/`offset` pagination yet, since
    the dataset stays small at this phase. Kept as a separate field anyway
    since that's the contract a future paginated implementation should
    already match, so callers don't need to change when it arrives.
    """

    documents: list[DocumentResponse]
    total: int
