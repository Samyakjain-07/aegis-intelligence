"""agentic_chunker.py's heuristic fallback path -- exercised directly since
no OPENAI_API_KEY is set in this environment (`_get_client()` returns
`None`, so `chunk_narrative_page` always takes the heuristic branch here;
see the module docstring for why that's an accepted degradation, not a
test gap). Tests the private `_heuristic_section_boundaries`/
`_enforce_size_bounds` helpers directly for precise boundary-arithmetic
assertions, plus the public `chunk_narrative_page`/`build_footnote_chunks`
entry points end-to-end.
"""
from __future__ import annotations

from src.chunking.agentic_chunker import (
    _MAX_CHARS_PER_CHUNK,
    _MIN_CHARS_PER_CHUNK,
    _enforce_size_bounds,
    _heuristic_section_boundaries,
    build_footnote_chunks,
    chunk_narrative_page,
)
from src.parsing.layout_segmenter import PageSegments


def test_heuristic_boundaries_are_ordered_and_nonoverlapping() -> None:
    text = "First paragraph about revenue.\n\nSecond paragraph about risk.\n\nThird paragraph."
    boundaries = _heuristic_section_boundaries(text)
    assert len(boundaries) == 3
    cursor = 0
    for start, end, _title in boundaries:
        assert start >= cursor
        assert end > start
        cursor = end
    # Every paragraph's own text survives intact inside its boundary.
    assert text[boundaries[0][0] : boundaries[0][1]] == "First paragraph about revenue."
    assert text[boundaries[2][0] : boundaries[2][1]] == "Third paragraph."


def test_heuristic_boundaries_on_text_with_no_blank_lines() -> None:
    text = "One single unbroken block of narrative text with no paragraph breaks at all."
    boundaries = _heuristic_section_boundaries(text)
    assert boundaries == [(0, len(text), None)]


def test_enforce_size_bounds_never_exceeds_max_chunk_size() -> None:
    long_word_salad = " ".join(f"word{i}" for i in range(2000))  # comfortably over the cap
    boundaries = [(0, len(long_word_salad), None)]
    bounded = _enforce_size_bounds(long_word_salad, boundaries)
    assert len(bounded) > 1
    for start, end, _title in bounded:
        assert end - start <= _MAX_CHARS_PER_CHUNK
    # Split on a space, not mid-word: every piece after the first starts
    # right after whitespace (or at 0), never inside a "wordN" token.
    for start, _end, _title in bounded[1:]:
        assert long_word_salad[start - 1] == " "


def test_enforce_size_bounds_merges_slivers() -> None:
    text = "ab" * 5000  # content irrelevant; only offsets matter here
    tiny_boundaries = [(0, 5, None), (5, 8, None), (8, 4000, None)]
    assert (tiny_boundaries[0][1] - tiny_boundaries[0][0]) < _MIN_CHARS_PER_CHUNK
    merged = _enforce_size_bounds(text, tiny_boundaries)
    # The two slivers (5 chars, 3 chars) merge into the first real chunk
    # rather than surviving as their own near-empty entries.
    assert merged[0][0] == 0
    assert all((end - start) >= _MIN_CHARS_PER_CHUNK or i == len(merged) - 1 for i, (start, end, _t) in enumerate(merged))


def test_chunk_narrative_page_uses_heuristic_without_an_api_key() -> None:
    text = "Management discussion.\n\n" + ("Risk factor detail. " * 400)
    drafts = chunk_narrative_page(page_number=7, text=text)
    assert drafts
    assert all(d.page_number == 7 for d in drafts)
    assert all(len(d.content) <= _MAX_CHARS_PER_CHUNK for d in drafts)
    assert all(d.content for d in drafts)  # no empty chunks


def test_chunk_narrative_page_empty_text_produces_no_chunks() -> None:
    assert chunk_narrative_page(page_number=1, text="   \n  ") == []


def test_build_footnote_chunks() -> None:
    page = PageSegments(page_number=4, narrative_text="body", footnote_text="(1) See appendix.", table_bboxes=[])
    drafts = build_footnote_chunks(page)
    assert len(drafts) == 1
    assert drafts[0].page_number == 4
    assert drafts[0].content == "(1) See appendix."


def test_build_footnote_chunks_empty() -> None:
    page = PageSegments(page_number=4, narrative_text="body", footnote_text="   ", table_bboxes=[])
    assert build_footnote_chunks(page) == []
