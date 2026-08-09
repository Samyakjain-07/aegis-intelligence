"""LLM-assisted query expansion -- `docs/architecture.md` §1 Pipeline B
step 2's multi-query stage, run *after* `history_manager.py`'s follow-up
reformulation so expansion always operates on a self-contained question,
never a follow-up fragment like "what about margins?"

**Provider decision:** OpenAI, reusing the vendor already approved for
`services/ingestion`'s `agentic_chunker.py` in Phase 5 -- see
`docs/DECISIONS_LOG.md`'s Phase 5 "Provider decisions" entry, which
explicitly left this open for Phase 6, and this phase's own entry for the
question asked (of Sam) and answered. Same optional-key,
deterministic-fallback pattern as that module: no `OPENAI_API_KEY` set /
the call fails / the response is unusable -> returns just the original
query, unexpanded, not a pipeline failure. Expansion is a *recall*
improvement, not a correctness-critical step -- `hybrid_retriever.py`
still runs the original query's own BM25+dense legs regardless, so
skipping expansion narrows recall, it doesn't break retrieval.
"""
from __future__ import annotations

import json
import logging
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

logger = logging.getLogger(__name__)

OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
OPENAI_CHAT_MODEL: str = os.environ.get("OPENAI_CHAT_MODEL", "gpt-4o-mini")

# Additional reformulations beyond the original, kept small on purpose:
# each one adds another full BM25+dense retrieval pair in
# hybrid_retriever.py, and this project's differentiator is grounded,
# verifiable answers, not maximal recall at any latency/cost.
_MAX_VARIANTS = 2

_client: OpenAI | None = None


def _get_client() -> OpenAI | None:
    global _client
    if not OPENAI_API_KEY:
        return None
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


_SYSTEM_PROMPT = (
    "You rewrite one financial-analyst question into alternative phrasings "
    f"that would surface the same information via search, up to {_MAX_VARIANTS} "
    "of them. Vary vocabulary/structure (synonyms for financial terms, "
    "active/passive voice) -- never change meaning, never introduce a new "
    "question, never narrow or broaden scope. Respond with JSON only: "
    '{"variants": ["...", ...]}.'
)


def expand_query(query_text: str) -> list[str]:
    """Returns `[query_text, *variants]` -- the original question always
    comes first (`hybrid_retriever.py` treats index 0 as primary, see its
    docstring), followed by up to `_MAX_VARIANTS` LLM-generated
    reformulations, or just `[query_text]` on a missing key or any
    failure.
    """
    client = _get_client()
    if client is None:
        return [query_text]
    try:
        response = client.chat.completions.create(
            model=OPENAI_CHAT_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": query_text},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            timeout=15,
        )
        raw = response.choices[0].message.content or "{}"
        payload = json.loads(raw)
        variants = [
            variant.strip()
            for variant in payload.get("variants", [])
            if isinstance(variant, str) and variant.strip()
        ]
        return [query_text, *variants[:_MAX_VARIANTS]]
    except Exception:
        logger.warning(
            "Multi-query expansion failed for %r; using the original query only.",
            query_text,
            exc_info=True,
        )
        return [query_text]
