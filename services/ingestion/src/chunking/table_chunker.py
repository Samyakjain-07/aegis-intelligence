"""Turns each `ExtractedTable` into one or more `TableChunkDraft`s --
never splitting a table mid-row.

The common case is one chunk per table (financial tables in a 10-K/10-Q
are typically a few dozen rows at most). `_MAX_ROWS_PER_CHUNK` exists for
the uncommon case (a large multi-year, multi-segment breakdown table):
past that row count, a table is split into consecutive **whole-row**
groups, each with the header repeated so every split part stays
independently interpretable on its own -- the split boundary is always
between two rows, never inside one, which is what "never splits a table
mid-row" actually means in code (as opposed to being trivially true only
because no test table was ever large enough to exercise the split path --
see `tests/unit/test_table_chunker.py`).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.parsing.table_extractor import ExtractedTable

_MAX_ROWS_PER_CHUNK = 60
# How many sample rows to render into the embedding-text summary below --
# keeps very large tables' embedding input bounded without needing every
# row represented (the full data is in raw_table_json regardless).
_EMBEDDING_SAMPLE_ROWS = 5


@dataclass(frozen=True, slots=True)
class TableChunkDraft:
    content: str  # embedding-oriented text summary -- see _embedding_text
    page_number: int
    table_index: int
    raw_table_json: dict[str, Any]
    row_count: int
    column_count: int


def _embedding_text(headers: list[str], rows: list[list[str]]) -> str:
    """A compact textual summary generated **only** as Cohere's embedding
    input -- Cohere still needs *some* string to vectorize, and a table
    can't be embedded as JSON meaningfully, but this is never what's
    stored or shown as the table's data. `raw_table_json`
    (`TableData.raw_table_json`) and Qdrant's payload both carry the full
    structured table; this flattened rendering exists purely so a
    semantic search for e.g. "data center revenue by quarter" can match
    against a table chunk at all. See `docs/DECISIONS_LOG.md` for why this
    doesn't violate the "never flatten a table" requirement -- that
    requirement is about the *stored* representation, not a disposable
    search-input rendering.
    """
    header_line = " | ".join(headers) if headers else ""
    row_lines = [" | ".join(str(cell) for cell in row) for row in rows[:_EMBEDDING_SAMPLE_ROWS]]
    parts = [part for part in [header_line, *row_lines] if part]
    return "\n".join(parts) if parts else "(empty table)"


def chunk_table(table: ExtractedTable) -> list[TableChunkDraft]:
    if table.row_count <= _MAX_ROWS_PER_CHUNK:
        return [
            TableChunkDraft(
                content=_embedding_text(table.headers, table.rows),
                page_number=table.page_number,
                table_index=table.table_index,
                raw_table_json=table.to_json(),
                row_count=table.row_count,
                column_count=table.column_count,
            )
        ]

    drafts: list[TableChunkDraft] = []
    for start in range(0, table.row_count, _MAX_ROWS_PER_CHUNK):
        row_slice = table.rows[start : start + _MAX_ROWS_PER_CHUNK]
        drafts.append(
            TableChunkDraft(
                content=_embedding_text(table.headers, row_slice),
                page_number=table.page_number,
                # Same table_index for every split part -- they're
                # fragments of ONE logical table, not distinct tables.
                # tasks/ingest_document.py's per-page chunk_index (not
                # table_index) is what keeps their DocumentChunk rows
                # distinct.
                table_index=table.table_index,
                raw_table_json={"headers": table.headers, "rows": row_slice},
                row_count=len(row_slice),
                column_count=table.column_count,
            )
        )
    return drafts


def chunk_tables(tables: list[ExtractedTable]) -> list[TableChunkDraft]:
    result: list[TableChunkDraft] = []
    for table in tables:
        result.extend(chunk_table(table))
    return result
