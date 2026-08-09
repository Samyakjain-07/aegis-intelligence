"""Follow-up reformulation -- `docs/architecture.md` §1 Pipeline B step
2's "follow-up? apply history-aware reformulation" branch. Rewrites a
follow-up question ("what about their margins?") into a self-contained
one ("What were NVIDIA's gross margins in Q4 FY24?") using the prior
turns of the same `Conversation`, so `hybrid_retriever.py` downstream has
something it can actually search on -- "their margins" alone shares
almost no vocabulary with the source text it needs to match.

Same OpenAI vendor / optional-key / deterministic-fallback pattern as
`multi_query.py` and `agentic_chunker.py` (Phase 5): no key / a failed
call -> returns the follow-up text completely unchanged, not a pipeline
failure. Unlike `multi_query.py`'s pure-recall tradeoff, skipping this
has a real retrieval-quality cost (a genuinely ambiguous follow-up may
retrieve nothing relevant) -- accepted for the same reason Phase 5
accepted `agentic_chunker.py`'s heuristic fallback: a degraded question is
still a real, answerable (if weaker) request, not a system failure.
"""
from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

logger = logging.getLogger(__name__)

OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
OPENAI_CHAT_MODEL: str = os.environ.get("OPENAI_CHAT_MODEL", "gpt-4o-mini")

# Prior turns beyond this many (most recent kept) are dropped -- bounds
# prompt size without full conversation summarization (out of Phase 6's
# scope); a follow-up almost always refers back to recent turns, not the
# start of a long thread.
_MAX_HISTORY_TURNS = 6

_client: OpenAI | None = None


def _get_client() -> OpenAI | None:
    global _client
    if not OPENAI_API_KEY:
        return None
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


_SYSTEM_PROMPT = (
    "You rewrite a financial analyst's follow-up question into a fully "
    "self-contained question, using the conversation history to resolve "
    "pronouns and implied subjects/companies/periods. Preserve the "
    "follow-up's actual intent exactly -- do not answer it, broaden it, or "
    "add assumptions the history doesn't support. If the follow-up is "
    "already self-contained, return it unchanged. Respond with the "
    "rewritten question only -- no explanation, no quotes."
)


def reformulate_followup(prior_turns: list[tuple[str, str]], follow_up_text: str) -> str:
    """`prior_turns` is `[(query_text, answer_text), ...]` in the order
    they were actually asked -- matches `Conversation.queries`'
    `order_by="Query.created_at"` (see `api/v1/routes/query.py` for where
    these come from). Returns the reformulated, self-contained question,
    or `follow_up_text` unchanged if there's no history to reformulate
    against, no `OPENAI_API_KEY`, or the call fails.
    """
    if not prior_turns:
        return follow_up_text
    client = _get_client()
    if client is None:
        return follow_up_text

    history_lines: list[str] = []
    for question, answer in prior_turns[-_MAX_HISTORY_TURNS:]:
        history_lines.append(f"Analyst: {question}")
        history_lines.append(f"Assistant: {answer}")
    history_block = "\n".join(history_lines)
    user_content = f"Conversation so far:\n{history_block}\n\nFollow-up question: {follow_up_text}"

    try:
        response = client.chat.completions.create(
            model=OPENAI_CHAT_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0,
            timeout=15,
        )
        rewritten = (response.choices[0].message.content or "").strip()
        return rewritten or follow_up_text
    except Exception:
        logger.warning(
            "Follow-up reformulation failed; using the follow-up text unchanged.", exc_info=True
        )
        return follow_up_text
