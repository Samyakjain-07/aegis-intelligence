"""Cohere embeddings for both narrative and table chunks --
`docs/architecture.md` §1 step 6 ("Both narrative chunks and table
representations are embedded").

**Provider decision (asked of Sam directly during this phase, per
`CLAUDE.md` §4):** Cohere, not a new vendor -- `cohere>=5.5` is already an
agreed dependency (`services/api`'s Cohere reranker), so using it for
embeddings too means one API key and one vendor relationship covers both,
instead of adding OpenAI/HuggingFace on top of Cohere. Model is
`embed-english-v3.0` by default (overridable via `COHERE_EMBED_MODEL`),
1024-dimensional -- `qdrant_writer.py`'s collection is created with that
dimension.

`input_type` matters here and is *not* optional in Cohere's v3 embed
models: `"search_document"` for ingestion-time content (this module's only
caller today), `"search_query"` for a future query-time embed call
(Phase 6) -- passing the wrong one measurably hurts retrieval quality
since the two input types are trained with different instruction
prefixes internally.
"""
from __future__ import annotations

import os
from typing import Literal

import cohere
from dotenv import load_dotenv

load_dotenv()

COHERE_API_KEY: str = os.environ.get("COHERE_API_KEY", "")
COHERE_EMBED_MODEL: str = os.environ.get("COHERE_EMBED_MODEL", "embed-english-v3.0")
EMBEDDING_DIMENSION = 1024  # fixed output size of embed-english-v3.0 / embed-multilingual-v3.0

# Cohere's embed-v3 models cap texts-per-call; batching keeps a
# whole-document embed pass (potentially hundreds of chunks) within that
# limit without the caller needing to know about it.
_BATCH_SIZE = 96

InputType = Literal["search_document", "search_query"]

_client: cohere.ClientV2 | None = None


def _get_client() -> cohere.ClientV2:
    global _client
    if not COHERE_API_KEY:
        raise RuntimeError("COHERE_API_KEY is not set; embedder.py cannot embed chunks without it.")
    if _client is None:
        _client = cohere.ClientV2(api_key=COHERE_API_KEY)
    return _client


def embed_texts(texts: list[str], input_type: InputType = "search_document") -> list[list[float]]:
    """Embeds `texts` in `_BATCH_SIZE`-sized batches, preserving input
    order (`tasks/ingest_document.py` zips this output back against the
    chunk list it came from). Raises on API failure rather than degrading
    silently -- unlike `agentic_chunker.py`'s LLM call, there is no
    meaningful fallback for a missing embedding: a chunk written to
    Postgres without a corresponding Qdrant vector would be permanently
    unretrievable, which `docs/architecture.md` §3's "if the provider is
    down, fail the ingestion job cleanly (don't partially embed)" failure
    path explicitly calls for.
    """
    if not texts:
        return []
    client = _get_client()
    vectors: list[list[float]] = []
    for start in range(0, len(texts), _BATCH_SIZE):
        batch = texts[start : start + _BATCH_SIZE]
        response = client.embed(
            model=COHERE_EMBED_MODEL,
            input_type=input_type,
            texts=batch,
            embedding_types=["float"],
        )
        floats = response.embeddings.float_
        if floats is None:
            raise RuntimeError("Cohere embed response did not include float embeddings.")
        vectors.extend(floats)
    return vectors
