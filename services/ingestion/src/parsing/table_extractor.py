"""Structured table extraction via camelot -- `docs/architecture.md` §1
step 4: "Tables are extracted into a structured representation (rows,
columns, headers preserved) -- never flattened into prose." This is the
direct implementation of that requirement: `ExtractedTable` keeps headers
and rows as separate lists all the way through to `TableData.raw_table_json`
(`services/api/src/models/db/table_data.py`); nothing in this module ever
joins a table into one string.

Only runs against pages `layout_segmenter.py` already flagged as table
candidates (via pymupdf's fast `find_tables()` detector) -- camelot is
comparatively slow (it re-renders/re-parses the PDF itself), so scoping it
to a handful of candidate pages instead of the whole document is a
deliberate cost control, not a correctness shortcut.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import camelot

logger = logging.getLogger(__name__)

# camelot's own `parsing_report["accuracy"]` is 0-100. Below this, a
# "lattice" (ruled-line) result is treated as unreliable and the page is
# retried with "stream" (whitespace-aligned) parsing instead -- lattice
# silently produces low-accuracy garbage on borderless tables rather than
# raising, so accuracy score (not an exception) is the signal to fall back.
_MIN_ACCURACY = 50.0


@dataclass(frozen=True, slots=True)
class ExtractedTable:
    page_number: int
    table_index: int  # 0-based ordinal among tables on this page
    headers: list[str]
    rows: list[list[str]]
    flavor: str  # "lattice" | "stream" -- which camelot parser produced this

    @property
    def row_count(self) -> int:
        return len(self.rows)

    @property
    def column_count(self) -> int:
        if self.headers:
            return len(self.headers)
        return len(self.rows[0]) if self.rows else 0

    def to_json(self) -> dict[str, Any]:
        """The structured shape stored in `TableData.raw_table_json` --
        headers and rows as separate lists, never flattened."""
        return {"headers": self.headers, "rows": self.rows}


def _to_extracted_table(table: Any, flavor: str) -> ExtractedTable:
    values = table.df.values.tolist()
    if not values:
        return ExtractedTable(
            page_number=int(table.page), table_index=int(table.order) - 1,
            headers=[], rows=[], flavor=flavor,
        )
    headers = [str(cell).strip() for cell in values[0]]
    rows = [[str(cell).strip() for cell in row] for row in values[1:]]
    return ExtractedTable(
        page_number=int(table.page),
        table_index=int(table.order) - 1,
        headers=headers,
        rows=rows,
        flavor=flavor,
    )


def extract_tables(pdf_path: Path, page_numbers: list[int]) -> list[ExtractedTable]:
    """Runs camelot against exactly `page_numbers` (1-indexed, as produced
    by `DocumentSegments.table_page_numbers`). Tries `flavor="lattice"`
    first (the common case for SEC filings' ruled tables); any table it
    finds below `_MIN_ACCURACY` is dropped and re-attempted with
    `flavor="stream"` instead. Returns `[]` (never raises) if
    `page_numbers` is empty or camelot finds nothing usable on either
    pass -- a document with no detected tables is a normal outcome, not a
    pipeline failure.
    """
    if not page_numbers:
        return []

    pages_arg = ",".join(str(p) for p in page_numbers)
    good: list[ExtractedTable] = []
    low_confidence_pages: set[int] = set()

    try:
        lattice_found = camelot.read_pdf(
            str(pdf_path), pages=pages_arg, flavor="lattice", suppress_stdout=True
        )
    except Exception:
        logger.warning("camelot flavor=lattice failed on %s", pdf_path, exc_info=True)
        lattice_found = []

    for table in lattice_found:
        if table.accuracy < _MIN_ACCURACY:
            low_confidence_pages.add(int(table.page))
            continue
        good.append(_to_extracted_table(table, "lattice"))

    retry_pages = sorted(
        p for p in low_confidence_pages if p not in {t.page_number for t in good}
    )
    if retry_pages:
        try:
            stream_found = camelot.read_pdf(
                str(pdf_path),
                pages=",".join(str(p) for p in retry_pages),
                flavor="stream",
                suppress_stdout=True,
            )
        except Exception:
            logger.warning("camelot flavor=stream fallback failed on %s", pdf_path, exc_info=True)
            stream_found = []
        for table in stream_found:
            good.append(_to_extracted_table(table, "stream"))

    return good
