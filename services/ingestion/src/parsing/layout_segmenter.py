"""Layout-aware split of each page into narrative text, table regions, and
footnotes -- `docs/architecture.md` §1 step 3, "the step that matters most
for accuracy: a financial table parsed as plain text loses its row/column
relationships, which is exactly what causes numeric hallucinations later."

Consumes `pdf_parser.py`'s `ParsedDocument` (font-annotated text lines +
pymupdf's candidate table bboxes) and produces, per page: narrative text
with table regions excluded (so a table's cell text never also shows up
duplicated inside a narrative chunk), footnote text, and the list of table
bboxes to hand to `table_extractor.py`. This module owns the
*classification* logic (is this line a footnote? does it belong to a
table?); it doesn't re-derive pymupdf primitives itself -- see
`pdf_parser.py`'s docstring for that division of responsibility.
"""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass

from src.parsing.pdf_parser import BBox, ParsedDocument, ParsedPage, TextLine

# A line's font is "small" if its median span size is at or below this
# fraction of the page's own body-text size -- computed per page (not a
# fixed point size) since body font size varies across filings/decks.
_FOOTNOTE_SIZE_RATIO = 0.85
# ... AND it sits in the bottom quarter of the page.
_FOOTNOTE_Y_RATIO = 0.75
# Leading footnote markers ("(1)", "*", "1.") are a strong signal on their
# own, regardless of position/size -- SEC filings sometimes put a
# footnote-marked line above the bottom-quarter cutoff.
_FOOTNOTE_MARKER_RE = re.compile(r"^\s*(\(\d+\)|\*+|\d{1,2}\.)\s+\S")


@dataclass(frozen=True, slots=True)
class PageSegments:
    page_number: int
    narrative_text: str
    footnote_text: str
    table_bboxes: list[BBox]

    @property
    def has_candidate_table(self) -> bool:
        return bool(self.table_bboxes)


@dataclass(frozen=True, slots=True)
class DocumentSegments:
    pages: list[PageSegments]

    @property
    def table_page_numbers(self) -> list[int]:
        return [p.page_number for p in self.pages if p.has_candidate_table]


def _overlaps(a: BBox, b: BBox) -> bool:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1


def _body_font_size(lines: list[TextLine]) -> float:
    sizes = [line.median_font_size for line in lines if line.text.strip() and line.median_font_size > 0]
    return statistics.median(sizes) if sizes else 10.0


def _is_footnote(line: TextLine, body_size: float, page_height: float) -> bool:
    if _FOOTNOTE_MARKER_RE.match(line.text):
        return True
    small = 0 < line.median_font_size <= body_size * _FOOTNOTE_SIZE_RATIO
    near_bottom = line.bbox[1] >= page_height * _FOOTNOTE_Y_RATIO
    return small and near_bottom


def segment_page(page: ParsedPage) -> PageSegments:
    body_size = _body_font_size(page.lines)
    narrative_parts: list[str] = []
    footnote_parts: list[str] = []
    for line in page.lines:
        if not line.text.strip():
            continue
        if any(_overlaps(line.bbox, table_bbox) for table_bbox in page.table_bboxes):
            continue  # belongs to a table region -- table_extractor.py owns this text
        if _is_footnote(line, body_size, page.height):
            footnote_parts.append(line.text)
        else:
            narrative_parts.append(line.text)
    return PageSegments(
        page_number=page.page_number,
        narrative_text="\n".join(narrative_parts),
        footnote_text="\n".join(footnote_parts),
        table_bboxes=page.table_bboxes,
    )


def segment_document(parsed: ParsedDocument) -> DocumentSegments:
    return DocumentSegments(pages=[segment_page(page) for page in parsed.pages])
