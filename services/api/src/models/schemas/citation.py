"""Pydantic response schemas for the `citations` route.

Mirrors `models.db.citation.Citation` field-for-field -- see
`docs/architecture.md` §7 (`ANSWER ||--o{ CITATION : cites`,
`DOCUMENTCHUNK ||--o{ CITATION : referenced_by`). `model_config =
ConfigDict(from_attributes=True)` is set now, ahead of any route actually
querying the DB, so Phase 6's `citation_resolver.py` can return an ORM
`Citation` instance directly and have FastAPI serialize it without a
separate manual-mapping step later.
"""
from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class CitationResponse(BaseModel):
    """One evidence pointer, as shown to the user alongside an answer."""

    model_config = ConfigDict(from_attributes=True)

    citation_id: uuid.UUID
    answer_id: uuid.UUID
    chunk_id: uuid.UUID
    exact_location: str
    snippet: str
