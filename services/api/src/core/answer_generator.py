"""Grounded answer generation -- `docs/architecture.md` §1 Pipeline B's
generation step. The one hard rule this module exists to enforce: no
claim beyond what's in the retrieved context, and every claim attributed
to a bracketed citation index (`[1]`, `[2]`, ...) matching the 1-based
position of the chunk it's drawn from in `chunks` -- the same positional
numbering `numeric_verifier.py` and `citation_resolver.py` both rely on
(see `numeric_verifier.py`'s docstring for why that shared numbering
matters).

**Provider decision:** OpenAI (same vendor decision as `multi_query.py`/
`history_manager.py` -- see `docs/DECISIONS_LOG.md`). No `OPENAI_API_KEY`
set / the call fails -> falls back to a deterministic **extractive**
answer (the top reranked chunks' own content, concatenated with citation
markers, zero synthesis) rather than failing the request outright. This
is a *stronger* guarantee than `multi_query.py`/`history_manager.py`'s
fallbacks: an extractive answer can only ever contain text that was
literally in a cited source, so it's trivially grounded by construction
-- a worse answer (no cross-chunk synthesis, no natural-language framing
of the numbers), never a less-grounded one.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import OpenAI

from src.core.types import RetrievedChunk
from src.observability.tracing import traced_stage

load_dotenv()

logger = logging.getLogger(__name__)

OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
OPENAI_CHAT_MODEL: str = os.environ.get("OPENAI_CHAT_MODEL", "gpt-4o-mini")

NO_CONTEXT_MESSAGE = (
    "I couldn't find relevant information in the ingested documents to "
    "answer this question. Try rephrasing it, or confirm the relevant "
    "filing has finished processing in the Library."
)

_client: OpenAI | None = None


def _get_client() -> OpenAI | None:
    global _client
    if not OPENAI_API_KEY:
        return None
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


_SYSTEM_PROMPT = (
    "You are a financial research assistant answering questions strictly "
    "from the numbered context below. Rules, no exceptions:\n"
    "1. Use ONLY the provided context -- never use outside knowledge, "
    "never guess, never estimate a figure that isn't stated.\n"
    "2. Every factual claim, especially every number, must be immediately "
    'followed by the bracket number of the context item it came from, e.g. '
    '"revenue grew 27% [2]." Use the exact bracket number shown for each '
    "context item -- never renumber or invent one.\n"
    "3. Copy numeric figures exactly as they appear in the source -- do "
    "not round, recompute, or convert units.\n"
    "4. If the context doesn't contain enough information to answer, say "
    "so explicitly rather than filling the gap with outside knowledge or "
    "inference.\n"
    "5. Write in clear, concise analyst prose."
)


@dataclass(frozen=True, slots=True)
class GeneratedAnswer:
    answer_text: str
    used_llm: bool  # False when the extractive fallback path produced this


def _build_context_block(chunks: list[RetrievedChunk]) -> str:
    parts = []
    for index, chunk in enumerate(chunks, start=1):
        label = (
            f"{chunk.ticker} {chunk.document_type.value}, "
            f"{chunk.document_title}, p.{chunk.page_number}"
        )
        parts.append(f"[{index}] ({label}, {chunk.chunk_type.value})\n{chunk.content}")
    return "\n\n".join(parts)


def _extractive_fallback(chunks: list[RetrievedChunk]) -> str:
    """No-LLM-key/failed-call answer: the top chunks' own content,
    unmodified, each tagged with its citation marker -- no synthesis, but
    every word is literally sourced by construction, so it needs no
    numeric verification to trust. Capped at the top 3 chunks so the
    fallback answer stays readable rather than dumping every retrieved
    chunk verbatim."""
    lines = [f"{chunk.content.strip()} [{index}]" for index, chunk in enumerate(chunks[:3], start=1)]
    return "\n\n".join(lines)


@traced_stage("answer_generator.generate_answer", run_type="llm")
def generate_answer(query_text: str, chunks: list[RetrievedChunk]) -> GeneratedAnswer:
    """`chunks` should already be the final, reranked, trimmed context
    (`reranker.py`'s output) -- this module doesn't retrieve or filter
    anything itself, only generates from what it's given, numbered in the
    order given."""
    if not chunks:
        return GeneratedAnswer(answer_text=NO_CONTEXT_MESSAGE, used_llm=False)

    client = _get_client()
    if client is None:
        logger.info("OPENAI_API_KEY not set; using the extractive fallback answer.")
        return GeneratedAnswer(answer_text=_extractive_fallback(chunks), used_llm=False)

    context_block = _build_context_block(chunks)
    try:
        response = client.chat.completions.create(
            model=OPENAI_CHAT_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Context:\n{context_block}\n\nQuestion: {query_text}",
                },
            ],
            temperature=0,
            timeout=30,
        )
        answer_text = (response.choices[0].message.content or "").strip()
        if not answer_text:
            raise ValueError("LLM returned an empty answer")
        return GeneratedAnswer(answer_text=answer_text, used_llm=True)
    except Exception:
        logger.warning(
            "Answer generation LLM call failed; using the extractive fallback answer.", exc_info=True
        )
        return GeneratedAnswer(answer_text=_extractive_fallback(chunks), used_llm=False)
