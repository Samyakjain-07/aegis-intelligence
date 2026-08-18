"""`GET /compare/metric` -- real implementation backing
`docs/architecture.md` §8 UC5 ("Compare metrics across quarters"): the
same line-item, across every ingested filing for one company, so the
Compare page can render a real cross-quarter table instead of
`MOCK_METRICS`.

Not tenant-scoped -- same reasoning as `documents.py`'s Phase 4
`GET /documents`: `Document`/`Company` are shared reference data (public
SEC filings), with no relationship to `Organization` in the ER model.
`tenant` stays in the signature anyway, matching every other route since
Phase 3 (the DI wiring is part of the API surface).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy.orm import Session

from src.api.v1.deps import TenantContext, get_db, get_tenant_context
from src.core.metric_comparator import find_metric_across_documents
from src.models.schemas.compare import (
    CompareMetricPeriodResponse,
    CompareMetricResponse,
)

router = APIRouter(prefix="/compare", tags=["compare"])


@router.get("/metric", response_model=CompareMetricResponse)
def compare_metric(
    ticker: str = Query(..., min_length=1, max_length=10, description="Company ticker, e.g. NVDA."),
    metric: str = Query(
        ..., min_length=1, max_length=200, description="Line-item label to search for, e.g. 'Revenue'."
    ),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
) -> CompareMetricResponse:
    """404s when `ticker` matches no ingested `Company` -- there's nothing
    to compare, as opposed to a 200 with an empty `periods` list (which is
    the correct response when the company exists but `metric` matched no
    row anywhere, a genuinely different case the frontend should be able
    to tell apart: "wrong ticker" vs. "right ticker, metric not found")."""
    company, matches = find_metric_across_documents(db, ticker, metric)
    if company is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"No ingested company found for ticker {ticker.strip().upper()!r}.",
        )

    return CompareMetricResponse(
        ticker=company.ticker,
        company_name=company.name,
        metric_query=metric,
        periods=[
            CompareMetricPeriodResponse(
                document_id=match.document.document_id,
                document_title=match.document.title,
                document_type=match.document.document_type,
                fiscal_year=match.document.fiscal_year,
                fiscal_quarter=match.document.fiscal_quarter,
                page_number=match.page_number,
                matched_row_label=match.matched_row_label,
                headers=match.headers,
                values=match.values,
                exact_location=match.exact_location,
            )
            for match in matches
        ],
    )
