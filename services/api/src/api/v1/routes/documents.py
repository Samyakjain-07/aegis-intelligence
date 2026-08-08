"""`GET/POST /documents` -- real DB-backed implementation.

Phase 4 (`PROJECT_HANDBOOK.md`): the document corpus is shared reference
data across every org, not owned by one -- SEC filings are public data,
and `docs/architecture.md` §7's ER diagram has no relationship at all
between `ORGANIZATION` and `COMPANY`/`DOCUMENT`. `GET /documents` therefore
does not filter by `tenant.org_id` (see `docs/DECISIONS_LOG.md`'s Phase 4
entry for the full reasoning and the alternative that was considered and
rejected). `POST /documents` accepts a real multipart PDF upload, resolves
(or creates) the filing's `Company` by ticker, writes a `Document` row
with `status=PENDING`, saves the PDF to local disk, and enqueues the Phase
4 stub Celery task -- real ingestion is Phase 5.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi import status as http_status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from src.api.v1.deps import TenantContext, get_db, get_tenant_context
from src.infra.celery_app import ingest_document_stub
from src.infra.storage import save_uploaded_pdf
from src.models.db.company import Company
from src.models.db.document import Document
from src.models.db.enums import DocumentStatus, DocumentType
from src.models.schemas.document import DocumentListResponse, DocumentResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

_ALLOWED_CONTENT_TYPES = {"application/pdf"}


@router.get("", response_model=DocumentListResponse)
def list_documents(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
) -> DocumentListResponse:
    """Every ingested `Document`, newest upload first.

    Not filtered by `tenant.org_id` -- see the module docstring. `tenant`
    stays in the signature anyway, matching every other route since Phase
    3 (see that phase's decisions-log entry: the DI wiring is part of the
    API surface), and because a per-tenant *visibility* toggle over the
    shared corpus (as opposed to ownership) is a plausible Phase 7 admin
    feature, not something this route should have to change shape for
    later.
    """
    rows = (
        db.execute(
            select(Document)
            .options(joinedload(Document.company))
            .order_by(Document.upload_date.desc(), Document.document_id.desc())
        )
        .scalars()
        .all()
    )
    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(row) for row in rows],
        total=len(rows),
    )


@router.post("", response_model=DocumentResponse, status_code=http_status.HTTP_201_CREATED)
async def create_document(
    file: Annotated[UploadFile, File(description="Raw PDF of the filing, transcript, or deck.")],
    ticker: Annotated[str, Form(min_length=1, max_length=10)],
    document_type: Annotated[DocumentType, Form()],
    fiscal_year: Annotated[int, Form()],
    fiscal_quarter: Annotated[int | None, Form(ge=1, le=4)] = None,
    company_name: Annotated[str | None, Form(max_length=255)] = None,
    sector: Annotated[str | None, Form(max_length=100)] = None,
    title: Annotated[str | None, Form(max_length=512)] = None,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
) -> DocumentResponse:
    """Creates a real `Document` row (`status=pending`), persists the PDF
    to local disk, and enqueues the Phase 4 stub ingestion task.

    Every field besides `file` is its own `Form(...)` parameter rather than
    one Pydantic submodel -- see the schema module's docstring for why
    (a submodel sibling to `File(...)` gets nested under its own key
    instead of flattening, which doesn't match a plain HTML form post).
    `fiscal_quarter`'s `ge=1, le=4` mirrors `Document`'s own `CHECK`
    constraint (`fiscal_quarter_range`) so a bad value 422s at the API
    boundary instead of failing in Postgres.

    Company resolution is find-or-create by ticker rather than requiring a
    `company_id` up front -- there's no company-picker UI (or
    `GET /companies` endpoint) for the frontend to source one from yet.
    This has an accepted race: two concurrent uploads for a brand-new
    ticker could both miss the `SELECT` and then have one lose to
    `companies.ticker`'s unique constraint on `commit`. Not guarded against
    (e.g. `ON CONFLICT DO NOTHING` / `SELECT ... FOR UPDATE`) since it is
    low-probability for a single-analyst local-dev/demo workload and easy
    to retry from the client if it ever happens; worth revisiting if this
    becomes a multi-writer production path.
    """
    if file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Expected a PDF (application/pdf), got {file.content_type!r}.",
        )

    normalized_ticker = ticker.strip().upper()
    company = (
        db.execute(select(Company).where(Company.ticker == normalized_ticker)).scalar_one_or_none()
    )
    if company is None:
        company = Company(
            ticker=normalized_ticker,
            name=company_name.strip() if company_name else normalized_ticker,
            sector=sector.strip() if sector else "Unknown",
        )
        db.add(company)
        db.flush()  # assigns company.company_id without a full commit yet

    document_id = uuid.uuid4()
    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty."
        )
    stored_path = save_uploaded_pdf(document_id, file.filename or "upload.pdf", content)

    document = Document(
        document_id=document_id,
        company_id=company.company_id,
        document_type=document_type,
        fiscal_quarter=fiscal_quarter,
        fiscal_year=fiscal_year,
        upload_date=datetime.now(timezone.utc).date(),
        source_url=stored_path,
        title=title.strip() if title else (file.filename or "Untitled document"),
        status=DocumentStatus.PENDING,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    try:
        ingest_document_stub.delay(str(document.document_id))
    except Exception:
        # A down/unreachable Redis shouldn't fail the write path -- the
        # row is already committed and correctly `PENDING`; a future
        # reconciliation pass (or a manual retry) can re-enqueue it. Failing
        # the whole request here would mean an infra hiccup in the async
        # side blocks the fast, decoupled write path this architecture
        # exists to protect (docs/architecture.md §3).
        logger.warning(
            "Failed to enqueue ingest_document task for %s", document.document_id, exc_info=True
        )

    return DocumentResponse.model_validate(document)
