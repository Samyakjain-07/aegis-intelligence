"""LLM-assisted narrative section-boundary chunking --
`docs/architecture.md` §1 step 5: "Narrative sections (MD&A, risk factors,
guidance) are chunked using an LLM-assisted pass that finds logical
section boundaries, rather than a fixed character count."

**Provider decision (asked of Sam directly during this phase, since
`CLAUDE.md` §4 requires stopping before adding a new external
dependency):** OpenAI's chat completions API, `gpt-4o-mini` by default
(overridable via `OPENAI_CHUNKING_MODEL`) -- cheap and fast enough to call
once per page without ingestion cost/latency becoming the bottleneck.

**No OPENAI_API_KEY set / the call fails / the response is unusable ->
falls back to a deterministic paragraph-boundary heuristic
(`_heuristic_section_boundaries`), not a pipeline failure.** This is a
deliberate deviation from `docs/architecture.md` §3's failure-path table,
which doesn't list a fallback for this stage specifically (only for
embedding and rerank). Section boundaries are a *quality* concern, not a
*correctness* one the way a wrong number is -- a document chunked on
paragraph breaks instead of LLM-identified topic boundaries is still
fully retrievable and citable, just with slightly less semantically clean
chunk edges. Failing the whole ingestion job over that would be a worse
tradeoff. See `docs/DECISIONS_LOG.md` for the full reasoning.
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import OpenAI

from src.parsing.layout_segmenter import PageSegments

load_dotenv()

logger = logging.getLogger(__name__)

OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
OPENAI_CHUNKING_MODEL: str = os.environ.get("OPENAI_CHUNKING_MODEL", "gpt-4o-mini")

# Keep a single LLM call's input small/cheap -- roughly a couple of dense
# filing pages. A page whose narrative text exceeds this skips the LLM
# call entirely and goes straight to the heuristic splitter rather than
# sending an oversized, expensive prompt.
_MAX_CHARS_PER_LLM_CALL = 6_000
# Hard ceiling on any single chunk, LLM- or heuristic-produced -- applied
# uniformly by `_enforce_size_bounds` so both paths give the same size
# guarantee to everything downstream (embedding batch sizing, context
# windows in Phase 6).
_MAX_CHARS_PER_CHUNK = 2_000
# Adjacent pieces smaller than this get merged into a neighbor rather than
# becoming their own near-empty chunk.
_MIN_CHARS_PER_CHUNK = 200

_client: OpenAI | None = None


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    content: str
    page_number: int
    section_title: str | None = None


def _get_client() -> OpenAI | None:
    global _client
    if not OPENAI_API_KEY:
        return None
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


_BOUNDARY_SYSTEM_PROMPT = (
    "You split one page of a SEC filing or earnings-call transcript into "
    "logical sections (e.g. MD&A subsections, individual risk factors, "
    "guidance remarks). Respond with JSON only, matching exactly: "
    '{"sections": [{"title": "<short title>", "start_char": <int>, '
    '"end_char": <int>}, ...]}. start_char/end_char are 0-indexed '
    "character offsets into the given text. Sections must be listed in "
    "order, must not overlap, and together must cover the entire input "
    "(every character belongs to exactly one section). Prefer natural "
    "paragraph/topic boundaries; never split in the middle of a sentence."
)

Boundary = tuple[int, int, str | None]


def _llm_section_boundaries(text: str) -> list[Boundary] | None:
    client = _get_client()
    if client is None:
        return None
    try:
        response = client.chat.completions.create(
            model=OPENAI_CHUNKING_MODEL,
            messages=[
                {"role": "system", "content": _BOUNDARY_SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            timeout=30,
        )
        raw = response.choices[0].message.content or "{}"
        payload = json.loads(raw)
        sections = payload["sections"]
        if not sections:
            raise ValueError("LLM returned zero sections")

        boundaries: list[Boundary] = []
        cursor = 0
        for section in sections:
            start, end = int(section["start_char"]), int(section["end_char"])
            if start < cursor or end <= start or end > len(text):
                raise ValueError(f"malformed/overlapping LLM section bounds: {section}")
            boundaries.append((start, end, section.get("title")))
            cursor = end
        return boundaries
    except Exception:
        logger.warning(
            "Agentic chunking LLM call failed or returned an unusable "
            "response; falling back to the heuristic splitter.",
            exc_info=True,
        )
        return None


_PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n")


def _heuristic_section_boundaries(text: str) -> list[Boundary]:
    """Splits on blank-line paragraph breaks. See module docstring for why
    this is an accepted fallback, not a failure."""
    boundaries: list[Boundary] = []
    start = 0
    for match in _PARAGRAPH_SPLIT_RE.finditer(text):
        end = match.start()
        if end > start:
            boundaries.append((start, end, None))
        start = match.end()
    if start < len(text):
        boundaries.append((start, len(text), None))
    return boundaries or [(0, len(text), None)]


@dataclass
class _MutableBoundary:
    start: int
    end: int
    title: str | None


def _merge_small_boundaries(boundaries: list[Boundary]) -> list[_MutableBoundary]:
    """Accumulates consecutive boundaries forward into a `pending` chunk
    until it reaches `_MIN_CHARS_PER_CHUNK`, then flushes it -- unlike a
    simple "merge into the previous entry" pass, this also handles a
    small *leading* piece (nothing earlier to merge into yet) correctly,
    by carrying it forward instead of emitting it as its own undersized
    chunk. Any small remainder left over at the very end (the loop ran out
    of boundaries before `pending` reached the minimum) is glued onto the
    last real chunk, or kept as the sole chunk if the whole page never
    reached the minimum at all.
    """
    merged: list[_MutableBoundary] = []
    pending: _MutableBoundary | None = None
    for start, end, title in boundaries:
        if pending is None:
            pending = _MutableBoundary(start, end, title)
        else:
            pending.end = end
        if pending.end - pending.start >= _MIN_CHARS_PER_CHUNK:
            merged.append(pending)
            pending = None
    if pending is not None:
        if merged:
            merged[-1].end = pending.end
        else:
            merged.append(pending)
    return merged


def _enforce_size_bounds(text: str, boundaries: list[Boundary]) -> list[Boundary]:
    merged = _merge_small_boundaries(boundaries)

    result: list[Boundary] = []
    for mb in merged:
        if mb.end - mb.start <= _MAX_CHARS_PER_CHUNK:
            result.append((mb.start, mb.end, mb.title))
            continue
        pos = mb.start
        while pos < mb.end:
            piece_end = min(pos + _MAX_CHARS_PER_CHUNK, mb.end)
            if piece_end < mb.end:
                whitespace = text.rfind(" ", pos, piece_end)
                if whitespace > pos:
                    piece_end = whitespace + 1  # keep the space as the trailing
                    # character of this piece so the next one doesn't start
                    # with a leading space.
            result.append((pos, piece_end, mb.title))
            pos = piece_end
    return result


def chunk_narrative_page(page_number: int, text: str) -> list[ChunkDraft]:
    """Splits one page's narrative text (already stripped of table/footnote
    regions by `layout_segmenter.py`) into `ChunkDraft`s. `chunk_index` is
    NOT assigned here -- `tasks/ingest_document.py` assigns one running
    counter per page across narrative, footnote, and table chunks
    together, since only the orchestrator sees all three streams merged
    (see that file's docstring)."""
    if not text.strip():
        return []
    boundaries = _llm_section_boundaries(text) if len(text) <= _MAX_CHARS_PER_LLM_CALL else None
    if boundaries is None:
        boundaries = _heuristic_section_boundaries(text)
    boundaries = _enforce_size_bounds(text, boundaries)

    drafts: list[ChunkDraft] = []
    for start, end, title in boundaries:
        content = text[start:end].strip()
        if content:
            drafts.append(ChunkDraft(content=content, page_number=page_number, section_title=title))
    return drafts


def build_footnote_chunks(page: PageSegments) -> list[ChunkDraft]:
    """One `FOOTNOTE` chunk per page holding all of that page's footnote
    text -- no LLM call, no further splitting. Footnotes are already
    granular (individual short lines from `layout_segmenter.py`), so a
    per-page grouping is the natural unit; a footnote section spanning
    more than `_MAX_CHARS_PER_CHUNK` on one page has never been observed
    in a real filing, so no size-bound enforcement is applied here."""
    text = page.footnote_text.strip()
    if not text:
        return []
    return [ChunkDraft(content=text, page_number=page.page_number, section_title="footnotes")]
