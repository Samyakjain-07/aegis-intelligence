"""Writes chunk embeddings + light, filterable metadata to Qdrant --
`docs/architecture.md` §1 step 7's vector-DB half of "Embeddings + light
metadata go into the vector DB (Qdrant); richer relational metadata ...
goes into the Postgres metadata store."

Point ID is the chunk's own `chunk_id` (as a UUID string, which Qdrant
accepts natively as a point ID) -- so `DocumentChunk.embedding_vector_id`
(Postgres) and a Qdrant point's `id` are always the same value by
construction, not by a lookup that could drift.

Payload includes `ticker`/`document_type`/`fiscal_year`/`fiscal_quarter`
plus the flattened `SourceLocation` (`loc_*` keys, see
`packages/shared/aegis_shared/source_location.py`) so Phase 6's hybrid
retrieval can filter Qdrant natively on any of these (`docs/
PROJECT_HANDBOOK.md` §2's stated reason for choosing Qdrant: "strong
native metadata filtering ... alongside vector search"). `ensure_collection`
creates payload indexes for exactly the fields that filtering benefit
applies to.
"""
from __future__ import annotations

import os
import uuid
from typing import Any

from aegis_shared.source_location import SourceLocation
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PayloadSchemaType, PointStruct, VectorParams

from src.embedding.embedder import EMBEDDING_DIMENSION

load_dotenv()

QDRANT_URL: str = os.environ.get("QDRANT_URL", "http://localhost:6335")
COLLECTION_NAME: str = os.environ.get("QDRANT_COLLECTION", "document_chunks")

_PAYLOAD_INDEXES: dict[str, PayloadSchemaType] = {
    "loc_document_id": PayloadSchemaType.KEYWORD,
    "ticker": PayloadSchemaType.KEYWORD,
    "document_type": PayloadSchemaType.KEYWORD,
    "loc_chunk_type": PayloadSchemaType.KEYWORD,
    "fiscal_year": PayloadSchemaType.INTEGER,
    "fiscal_quarter": PayloadSchemaType.INTEGER,
}

_client: QdrantClient | None = None


def _get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(url=QDRANT_URL)
    return _client


def ensure_collection(vector_size: int = EMBEDDING_DIMENSION) -> None:
    """Idempotent collection setup -- safe to call at the start of every
    ingestion run. Creates the collection (cosine distance, matching
    Cohere's recommended metric for embed-v3 models) and its payload
    indexes only the first time; every call after that is a cheap no-op
    check against `get_collections()`."""
    client = _get_client()
    existing = {c.name for c in client.get_collections().collections}
    if COLLECTION_NAME in existing:
        return
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )
    for field_name, schema in _PAYLOAD_INDEXES.items():
        client.create_payload_index(COLLECTION_NAME, field_name=field_name, field_schema=schema)


def upsert_chunk_vector(
    *,
    chunk_id: uuid.UUID,
    vector: list[float],
    content: str,
    source_location: SourceLocation,
    ticker: str,
    document_type: str,
    fiscal_year: int,
    fiscal_quarter: int | None,
) -> None:
    """Upserts one point. `wait=True` -- ingestion is an offline batch
    job, not a latency-sensitive path, so it's worth waiting for Qdrant to
    confirm the write before `tasks/ingest_document.py` goes on to record
    `embedding_vector_id` in Postgres; otherwise a crash between the two
    writes could leave a `DocumentChunk` pointing at a vector that isn't
    actually there yet.
    """
    client = _get_client()
    payload: dict[str, Any] = {
        "content": content,
        "ticker": ticker,
        "document_type": document_type,
        "fiscal_year": fiscal_year,
        "fiscal_quarter": fiscal_quarter,
        **source_location.to_qdrant_payload(),
    }
    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[PointStruct(id=str(chunk_id), vector=vector, payload=payload)],
        wait=True,
    )
