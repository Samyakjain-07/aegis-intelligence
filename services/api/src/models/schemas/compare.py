"""Pydantic response schemas for `GET /compare/metric`
(`docs/architecture.md` §8 UC5, "Compare metrics across quarters").

`CompareMetricPeriodResponse` deliberately carries `headers`/`values` as
parallel lists straight from `TableData.raw_table_json`, not one flattened
display string -- the same "never flatten a table" principle
`table_extractor.py`/`numeric_verifier.py` already hold to (`CLAUDE.md`
§1). Letting the frontend zip `headers`/`values` itself keeps whatever
column structure the source table actually had (a filing's comparative
columns -- e.g. current period vs. the prior-year period -- don't collapse
into one number).
"""
from __future__ import annotations

import uuid

from pydantic import BaseModel

from src.models.db.enums import DocumentType


class CompareMetricPeriodResponse(BaseModel):
    """One ingested filing's matched row for the requested metric. Absent
    entirely from `CompareMetricResponse.periods` for any filing where no
    table row matched -- not returned as a null/empty placeholder, since
    the Compare page only has something to plot for periods where the
    metric was actually found."""

    document_id: uuid.UUID
    document_title: str
    document_type: DocumentType
    fiscal_year: int
    fiscal_quarter: int | None
    page_number: int
    matched_row_label: str
    headers: list[str]
    values: list[str]
    exact_location: str


class CompareMetricResponse(BaseModel):
    """`GET /compare/metric` response envelope. `metric_query` echoes back
    exactly what the client asked for (not `matched_row_label`, which can
    legitimately differ per period/table) so the UI can show "results for
    'revenue'" even when zero periods matched."""

    ticker: str
    company_name: str
    metric_query: str
    periods: list[CompareMetricPeriodResponse]
