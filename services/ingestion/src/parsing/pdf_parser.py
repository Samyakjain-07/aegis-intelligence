"""pymupdf-based structural parse -- the one place `services/ingestion`
opens a PDF and reads its raw layout. Every downstream stage
(`document_classifier.py`, `layout_segmenter.py`, `table_extractor.py`)
consumes this module's output rather than touching pymupdf directly, so
there's exactly one place that knows how to walk a `pymupdf.Document`.

Extracts, per page: plain text (for classification), font-annotated text
lines (size + bold, for `layout_segmenter.py`'s narrative/footnote split),
and candidate table bounding boxes via pymupdf's own `Page.find_tables()`
-- a fast structural detector, deliberately *not* the final table
extraction (that's camelot, in `table_extractor.py`, which is slower but
markedly more accurate on ruled financial tables). Bundling the
table-bbox detection in here rather than `layout_segmenter.py` is a
pragmatic call: it needs the live `pymupdf.Page` object, which this module
already has in scope while iterating, and `layout_segmenter.py`'s job is
the narrative/footnote/table *classification* logic that consumes these
bboxes, not re-deriving pymupdf primitives itself.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

logger = logging.getLogger(__name__)

# pymupdf span "flags" is a bitmask; bit 4 (value 16) is "bold". See
# https://pymupdf.readthedocs.io/en/latest/textpage.html#span-flags -- the
# other bits (superscript/italic/serifed/monospaced) aren't used by any
# heuristic in this pipeline yet.
_BOLD_FLAG = 1 << 4

BBox = tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class TextSpan:
    text: str
    font_size: float
    bold: bool


@dataclass(frozen=True, slots=True)
class TextLine:
    """One visual line of text, with the font metadata
    `layout_segmenter.py` needs to tell body text apart from a footnote
    (smaller font, near the page bottom)."""

    text: str
    bbox: BBox
    spans: list[TextSpan] = field(default_factory=list)

    @property
    def median_font_size(self) -> float:
        sizes = sorted(s.font_size for s in self.spans if s.text.strip())
        if not sizes:
            return 0.0
        mid = len(sizes) // 2
        return sizes[mid] if len(sizes) % 2 else (sizes[mid - 1] + sizes[mid]) / 2

    @property
    def is_bold(self) -> bool:
        return bool(self.spans) and all(s.bold for s in self.spans if s.text.strip())


@dataclass(frozen=True, slots=True)
class ParsedPage:
    page_number: int  # 1-indexed, matching DocumentChunk.page_number
    width: float
    height: float
    raw_text: str
    lines: list[TextLine]
    table_bboxes: list[BBox]


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    source_path: Path
    page_count: int
    pages: list[ParsedPage]


def _extract_lines(page: pymupdf.Page) -> list[TextLine]:
    lines: list[TextLine] = []
    text_dict = page.get_text("dict")
    for block in text_dict.get("blocks", []):
        if block.get("type") != 0:  # 0 = text block, 1 = image block
            continue
        for line in block.get("lines", []):
            spans = [
                TextSpan(
                    text=span.get("text", ""),
                    font_size=float(span.get("size", 0.0)),
                    bold=bool(int(span.get("flags", 0)) & _BOLD_FLAG),
                )
                for span in line.get("spans", [])
            ]
            text = "".join(s.text for s in spans)
            if not text.strip():
                continue
            bbox = tuple(float(v) for v in line.get("bbox", (0.0, 0.0, 0.0, 0.0)))
            lines.append(TextLine(text=text, bbox=bbox, spans=spans))  # type: ignore[arg-type]
    return lines


def _find_table_bboxes(page: pymupdf.Page) -> list[BBox]:
    """Best-effort candidate-table detection. Wrapped in a broad
    try/except: `find_tables()` is a heuristic itself and known to raise
    on some malformed/unusual page content streams -- a detection failure
    here should degrade to "no table candidates on this page" (narrative
    text still gets extracted normally), not abort the whole document."""
    try:
        finder = page.find_tables()
        return [tuple(float(v) for v in t.bbox) for t in finder.tables]  # type: ignore[misc]
    except Exception:
        logger.warning("find_tables() failed on page %d; treating as no tables.", page.number + 1, exc_info=True)
        return []


def parse_pdf(path: Path) -> ParsedDocument:
    """Opens `path` and returns a page-by-page structural parse. Raises
    whatever pymupdf raises on a genuinely corrupt/unopenable file --
    deliberately not swallowed here, since that's exactly the
    `docs/architecture.md` §3 "corrupt or unparseable PDF" failure path,
    which `tasks/ingest_document.py`'s retry/dead-letter handling is
    responsible for, not this function.
    """
    pages: list[ParsedPage] = []
    with pymupdf.open(str(path)) as doc:
        for page in doc:
            pages.append(
                ParsedPage(
                    page_number=page.number + 1,
                    width=float(page.rect.width),
                    height=float(page.rect.height),
                    raw_text=page.get_text(),
                    lines=_extract_lines(page),
                    table_bboxes=_find_table_bboxes(page),
                )
            )
        page_count = doc.page_count
    return ParsedDocument(source_path=path, page_count=page_count, pages=pages)
