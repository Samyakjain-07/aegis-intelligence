"""layout_segmenter.py's narrative/table/footnote split, built on synthetic
`ParsedPage` fixtures so these tests don't need a real PDF."""
from __future__ import annotations

from src.parsing.layout_segmenter import segment_page
from src.parsing.pdf_parser import ParsedPage, TextLine, TextSpan

PAGE_HEIGHT = 792.0  # US Letter, points


def _line(text: str, y0: float, font_size: float = 10.0, bold: bool = False) -> TextLine:
    span = TextSpan(text=text, font_size=font_size, bold=bold)
    return TextLine(text=text, bbox=(72.0, y0, 500.0, y0 + font_size), spans=[span])


def test_body_text_becomes_narrative() -> None:
    page = ParsedPage(
        page_number=1, width=612.0, height=PAGE_HEIGHT, raw_text="",
        lines=[_line("Revenue grew 12% year over year.", y0=100.0, font_size=11.0)],
        table_bboxes=[],
    )
    segments = segment_page(page)
    assert "Revenue grew 12%" in segments.narrative_text
    assert segments.footnote_text == ""


def test_small_font_near_bottom_becomes_footnote() -> None:
    body = _line("Normal body paragraph text here.", y0=100.0, font_size=11.0)
    footnote = _line("See accompanying notes for detail.", y0=PAGE_HEIGHT * 0.9, font_size=7.0)
    page = ParsedPage(
        page_number=2, width=612.0, height=PAGE_HEIGHT, raw_text="", lines=[body, footnote], table_bboxes=[]
    )
    segments = segment_page(page)
    assert "Normal body paragraph" in segments.narrative_text
    assert "See accompanying notes" in segments.footnote_text
    assert "See accompanying notes" not in segments.narrative_text


def test_marker_prefixed_line_is_footnote_regardless_of_position() -> None:
    marked = _line("(1) This footnote happens to sit near the top of the page.", y0=80.0, font_size=11.0)
    page = ParsedPage(page_number=3, width=612.0, height=PAGE_HEIGHT, raw_text="", lines=[marked], table_bboxes=[])
    segments = segment_page(page)
    assert segments.footnote_text != ""
    assert segments.narrative_text == ""


def test_line_overlapping_table_bbox_is_excluded_from_narrative_and_footnote() -> None:
    table_bbox = (72.0, 200.0, 500.0, 400.0)
    inside_table = _line("Revenue | 100 | 120", y0=250.0, font_size=10.0)
    outside_table = _line("Discussion of results.", y0=100.0, font_size=11.0)
    page = ParsedPage(
        page_number=4, width=612.0, height=PAGE_HEIGHT, raw_text="",
        lines=[inside_table, outside_table], table_bboxes=[table_bbox],
    )
    segments = segment_page(page)
    assert "Revenue | 100 | 120" not in segments.narrative_text
    assert "Revenue | 100 | 120" not in segments.footnote_text
    assert "Discussion of results." in segments.narrative_text
    assert segments.table_bboxes == [table_bbox]
