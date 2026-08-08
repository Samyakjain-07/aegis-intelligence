"""Seed a handful of fake `Document` (+ backing `Company`) rows for local
testing of the Library page (`PROJECT_HANDBOOK.md` Phase 4).

Usage (from the repo root, with `services/api`'s venv activated so
SQLAlchemy/python-dotenv are importable):

    .\\services\\api\\venv\\Scripts\\Activate.ps1
    python scripts\\seed_dev_data.py

Idempotent: re-running skips any (company, document_type, fiscal_year,
fiscal_quarter) combination that already exists rather than duplicating
rows. This is an application-level check done here in the script, not a
database constraint -- the schema has no uniqueness rule over those
columns (and adding one wasn't asked for and isn't needed by any real
code path yet), so this only protects against *this script* being re-run,
not general duplicate inserts from elsewhere.

These rows are metadata-only -- there is no real PDF behind `source_url`
for any of them (unlike a document created through the real
`POST /documents` upload flow, which saves an actual file via
`src.infra.storage.save_uploaded_pdf`). They exist to make the Library
page's table, filters, and status badges look real while testing the
fetch/render path, not to be opened or ingested.
"""
from __future__ import annotations

import sys
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path

# scripts/seed_dev_data.py lives at the repo root's scripts/ dir, but the
# code it needs to import lives under services/api/src -- not on sys.path
# by default for a script invoked as `python scripts\seed_dev_data.py`
# from the repo root. Insert services/api (not services/api/src) so
# `import src...` resolves the same way it does for services/api's own
# tests and Alembic env.py.
_SERVICES_API = Path(__file__).resolve().parents[1] / "services" / "api"
sys.path.insert(0, str(_SERVICES_API))

from src.infra.db import SessionLocal
from src.models.db.company import Company
from src.models.db.document import Document
from src.models.db.enums import DocumentStatus, DocumentType


@dataclass(frozen=True)
class SeedCompany:
    ticker: str
    name: str
    sector: str


@dataclass(frozen=True)
class SeedDocument:
    ticker: str
    title: str
    document_type: DocumentType
    fiscal_year: int
    fiscal_quarter: int | None
    upload_date: date
    status: DocumentStatus


SEED_COMPANIES: list[SeedCompany] = [
    SeedCompany("NVDA", "NVIDIA Corporation", "Semiconductors"),
    SeedCompany("AMD", "Advanced Micro Devices, Inc.", "Semiconductors"),
    SeedCompany("INTC", "Intel Corporation", "Semiconductors"),
    SeedCompany("TSM", "Taiwan Semiconductor Manufacturing Company", "Semiconductors"),
]

# Mirrors the shape (tickers, doc types, dates, mixed statuses) of the old
# `MOCK_DOCS` array in frontend/src/app/pages/Library.tsx, so swapping mock
# data for real data doesn't change what the demo looks like on first run.
# `MOCK_DOCS`'s "Other" type has no equivalent in `DocumentType` (the enum
# has no generic bucket, by design -- see enums.py's decisions-log entry)
# so the TSM row below maps it to INVESTOR_DECK as the closest fit rather
# than inventing a fifth enum value outside the agreed stack.
SEED_DOCUMENTS: list[SeedDocument] = [
    SeedDocument(
        "NVDA",
        "NVDA Q4 FY24 Earnings Call Transcript",
        DocumentType.EARNINGS_TRANSCRIPT,
        2024,
        4,
        date(2024, 2, 21),
        DocumentStatus.COMPLETED,
    ),
    SeedDocument(
        "NVDA",
        "NVDA 10-K FY2024",
        DocumentType.FORM_10K,
        2024,
        None,
        date(2024, 2, 21),
        DocumentStatus.COMPLETED,
    ),
    SeedDocument(
        "AMD",
        "AMD Q4 2023 Earnings Call Transcript",
        DocumentType.EARNINGS_TRANSCRIPT,
        2023,
        4,
        date(2024, 1, 30),
        DocumentStatus.COMPLETED,
    ),
    SeedDocument(
        "AMD",
        "AMD 10-K 2023",
        DocumentType.FORM_10K,
        2023,
        None,
        date(2024, 1, 31),
        DocumentStatus.COMPLETED,
    ),
    SeedDocument(
        "INTC",
        "INTC Q1 2024 Earnings Deck",
        DocumentType.INVESTOR_DECK,
        2024,
        1,
        date(2024, 4, 25),
        DocumentStatus.PROCESSING,
    ),
    SeedDocument(
        "TSM",
        "TSM Q1 2024 Management Report",
        DocumentType.INVESTOR_DECK,
        2024,
        1,
        date(2024, 4, 18),
        DocumentStatus.COMPLETED,
    ),
]


def main() -> None:
    session = SessionLocal()
    created_companies = 0
    created_documents = 0
    skipped_documents = 0
    try:
        companies_by_ticker: dict[str, Company] = {}
        for seed in SEED_COMPANIES:
            company = session.query(Company).filter(Company.ticker == seed.ticker).one_or_none()
            if company is None:
                company = Company(ticker=seed.ticker, name=seed.name, sector=seed.sector)
                session.add(company)
                session.flush()  # assigns company.company_id for the documents below
                created_companies += 1
            companies_by_ticker[seed.ticker] = company

        for seed in SEED_DOCUMENTS:
            company = companies_by_ticker[seed.ticker]
            existing = (
                session.query(Document)
                .filter(
                    Document.company_id == company.company_id,
                    Document.document_type == seed.document_type,
                    Document.fiscal_year == seed.fiscal_year,
                    Document.fiscal_quarter == seed.fiscal_quarter,
                )
                .one_or_none()
            )
            if existing is not None:
                skipped_documents += 1
                continue

            document = Document(
                document_id=uuid.uuid4(),
                company_id=company.company_id,
                document_type=seed.document_type,
                fiscal_quarter=seed.fiscal_quarter,
                fiscal_year=seed.fiscal_year,
                upload_date=seed.upload_date,
                source_url=f"seed-data/{seed.ticker.lower()}-{seed.fiscal_year}"
                f"{f'-q{seed.fiscal_quarter}' if seed.fiscal_quarter else ''}.pdf",
                title=seed.title,
                status=seed.status,
            )
            session.add(document)
            created_documents += 1

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    print(
        f"Seed complete: {created_companies} company row(s) created, "
        f"{created_documents} document row(s) created, "
        f"{skipped_documents} document row(s) already present (skipped)."
    )


if __name__ == "__main__":
    main()
