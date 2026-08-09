"""packages/shared/aegis_shared/source_location.py -- exercised from here
since services/ingestion is where it's editable-installed
(`services/ingestion/requirements.txt`); services/api will get the same
coverage from its own test suite once Phase 6 installs it there too.
"""
from __future__ import annotations

import uuid

import pytest
from aegis_shared.source_location import SourceLocation


def test_table_chunk_requires_table_cell_ref() -> None:
    with pytest.raises(ValueError, match="table_cell_ref"):
        SourceLocation(document_id=uuid.uuid4(), page_number=1, chunk_type="table", chunk_index=0)


def test_narrative_chunk_exact_location_and_text_span() -> None:
    loc = SourceLocation(document_id=uuid.uuid4(), page_number=6, chunk_type="narrative", chunk_index=2)
    assert loc.text_span == "chunk 2"
    assert loc.exact_location() == "p.6 (narrative, chunk 2)"


def test_table_chunk_exact_location_uses_table_cell_ref() -> None:
    loc = SourceLocation(
        document_id=uuid.uuid4(), page_number=14, chunk_type="table", chunk_index=0, table_cell_ref="table 1"
    )
    assert loc.text_span is None
    assert loc.exact_location() == "p.14 (table 1)"


def test_qdrant_payload_round_trip() -> None:
    original = SourceLocation(
        document_id=uuid.uuid4(), page_number=3, chunk_type="table", chunk_index=1, table_cell_ref="table 0"
    )
    restored = SourceLocation.from_qdrant_payload(original.to_qdrant_payload())
    assert restored == original
