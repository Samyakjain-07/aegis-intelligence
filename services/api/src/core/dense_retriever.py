"""Dense (semantic) retrieval -- the vector half of hybrid search
(`docs/architecture.md` §1 Pipeline B step 3). Embeds the query with
Cohere, then searches Qdrant's `document_chunks` collection for nearest
neighbors.

**`input_type="search_query"`, not `"search_document"`:** Cohere's v3
embed models are trained with different instruction prefixes per
`input_type`; ingestion's `embedder.py` (Phase 5) embedded every stored
chunk with `"search_document"`, and using the wrong one here would still
run without erroring but would measurably hurt retrieval quality --
flagged as a concrete Phase 6 carry-over in `docs/progress.md`'s Phase 5
snapshot.

**Deliberately does not import `services/ingestion/src/embedding/
embedder.py`.** The two services are decoupled by design
(`docs/architecture.md` §3; established for `storage/models.py` in Phase
5's decisions log) -- they agree on the Cohere model name/vector
dimension by convention (the same env var names, `COHERE_EMBED_MODEL`),
never by importing each other's code. This module re-implements only the
one Cohere call it actually needs (single-text query embedding); it
doesn't need `embedder.py`'s batching logic, which exists for ingestion's
much larger, offline, many-chunks-per-call workload.
"""
from __future__ import annotations

import os
import uuid

import cohere
from dotenv import load_dotenv
from qdrant_client import QdrantClient

from src.core.types import RankedChunk

load_dotenv()

COHERE_API_KEY: str = os.environ.get("COHERE_API_KEY", "")
COHERE_EMBED_MODEL: str = os.environ.get("COHERE_EMBED_MODEL", "embed-english-v3.0")
QDRANT_URL: str = os.environ.get("QDRANT_URL", "http://localhost:6335")
QDRANT_COLLECTION: str = os.environ.get("QDRANT_COLLECTION", "document_chunks")

_cohere_client: cohere.ClientV2 | None = None
_qdrant_client: QdrantClient | None = None


def _get_cohere_client() -> cohere.ClientV2:
    global _cohere_client
    if not COHERE_API_KEY:
        raise RuntimeError("COHERE_API_KEY is not set; dense_retriever.py cannot embed a query without it.")
    if _cohere_client is None:
        _cohere_client = cohere.ClientV2(api_key=COHERE_API_KEY)
    return _cohere_client


def get_qdrant_client() -> QdrantClient:
    """Exported (not `_`-prefixed) because `citation_resolver.py` also
    needs a Qdrant client, for the same collection, to recover a table
    chunk's `table_cell_ref` -- see that module's docstring for why. One
    lazily-created client shared by both, rather than each module opening
    its own connection.
    """
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(url=QDRANT_URL)
    return _qdrant_client


def embed_query(query_text: str) -> list[float]:
    client = _get_cohere_client()
    response = client.embed(
        model=COHERE_EMBED_MODEL,
        input_type="search_query",
        texts=[query_text],
        embedding_types=["float"],
    )
    floats = response.embeddings.float_
    if not floats:
        raise RuntimeError("Cohere embed response did not include a float embedding for the query.")
    return floats[0]


def search(query_text: str, top_k: int = 30) -> list[RankedChunk]:
    """Embeds `query_text` and returns Qdrant's nearest neighbors,
    highest-similarity first. Raises on a Cohere/Qdrant failure rather
    than returning an empty list -- `hybrid_retriever.py` is the layer
    responsible for deciding whether a failed leg should degrade the
    overall request or not; this function shouldn't quietly pretend
    "found nothing" is the same thing as "the provider was unreachable."
    """
    if not query_text.strip():
        return []
    vector = embed_query(query_text)
    client = get_qdrant_client()
    result = client.query_points(
        collection_name=QDRANT_COLLECTION,
        query=vector,
        limit=top_k,
        with_payload=False,
    )
    return [RankedChunk(chunk_id=uuid.UUID(str(point.id)), score=float(point.score)) for point in result.points]
