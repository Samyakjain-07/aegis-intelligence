"""table_chunker.py's one hard requirement: a table is never split
mid-row. These tests build a synthetic `ExtractedTable` bigger than
`_MAX_ROWS_PER_CHUNK` and check the split points are exactly on row
boundaries -- not just "it happened to work" on a small fixture."""
from __future__ import annotations

from src.chunking.table_chunker import _MAX_ROWS_PER_CHUNK, chunk_table
from src.parsing.table_extractor import ExtractedTable


def _make_table(row_count: int) -> ExtractedTable:
    headers = ["Metric", "Q1", "Q2", "Q3", "Q4"]
    rows = [[f"Row {i}", str(i), str(i), str(i), str(i)] for i in range(row_count)]
    return ExtractedTable(page_number=12, table_index=0, headers=headers, rows=rows, flavor="lattice")


def test_small_table_is_a_single_chunk() -> None:
    table = _make_table(10)
    drafts = chunk_table(table)
    assert len(drafts) == 1
    assert drafts[0].row_count == 10
    assert drafts[0].raw_table_json["rows"] == table.rows


def test_large_table_splits_on_row_boundaries_only() -> None:
    total_rows = _MAX_ROWS_PER_CHUNK * 2 + 7
    table = _make_table(total_rows)
    drafts = chunk_table(table)

    # Every row from the original table appears exactly once, across all
    # drafts, in original order -- i.e. the split is a clean partition.
    reassembled = [row for draft in drafts for row in draft.raw_table_json["rows"]]
    assert reassembled == table.rows

    # No draft (except possibly the last) exceeds the row cap, and none is
    # a partial row -- every row in every draft is a full 5-cell row from
    # the original table, never a fragment.
    for draft in drafts[:-1]:
        assert draft.row_count == _MAX_ROWS_PER_CHUNK
    assert drafts[-1].row_count == total_rows - _MAX_ROWS_PER_CHUNK * (len(drafts) - 1)
    for draft in drafts:
        for row in draft.raw_table_json["rows"]:
            assert len(row) == table.column_count

    # Every split part stays independently interpretable: header carried
    # into each one, same table_index (they're fragments of one table).
    for draft in drafts:
        assert draft.raw_table_json["headers"] == table.headers
        assert draft.table_index == table.table_index


def test_empty_table_produces_one_empty_chunk() -> None:
    table = ExtractedTable(page_number=1, table_index=0, headers=[], rows=[], flavor="stream")
    drafts = chunk_table(table)
    assert len(drafts) == 1
    assert drafts[0].row_count == 0
    assert drafts[0].content == "(empty table)"
