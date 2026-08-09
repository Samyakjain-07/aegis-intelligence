"""Checks every numeric claim in a generated answer against the *exact*
source chunk/table it cites -- the literal implementation of `CLAUDE.md`
§1's core promise: "every number in an answer must be verified against
the actual source table before it's shown as confident."

Deliberately has **no LLM call in it anywhere** -- verifying a number by
asking another LLM "does this look right?" would just be trading one
hallucination-shaped risk for another (a verifier model can be wrong or
sycophantic too). This module is pure regex/arithmetic: extract numbers
from the claim, extract numbers from the one source the claim is
attributed to, and check for a real numeric match. Boring on purpose --
boring is what "verified," not "plausible," actually requires.

**Citation indices are 1-based and positional**, matching whatever order
`answer_generator.py` numbered its context in `[1]`, `[2]`, ... -- both
that module and this one are always called with the *same* `chunks` list
from `api/v1/routes/query.py`, so index `n` means "the (n-1)th element of
that list" in both places by construction, not by a value that travels
between them.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

from src.core.types import RetrievedChunk

# Scale words that multiply the digits they follow. "%"/"percent" are
# deliberately absent -- a percentage is compared against the source's raw
# digits directly (27% means "the digits 27 appear," not "27 scaled by
# some factor"), unlike "billion"/"million", which really do mean
# "multiply the written digits by 1e9/1e6."
_SCALE_MULTIPLIERS: dict[str, float] = {
    "billion": 1e9,
    "bn": 1e9,
    "million": 1e6,
    "mn": 1e6,
    "thousand": 1e3,
    "k": 1e3,
}

_NUMERIC_RE = re.compile(
    r"(?P<paren_open>\()?"
    r"(?P<sign>-)?"
    r"(?P<dollar>\$)?"
    r"(?P<int>\d{1,3}(?:,\d{3})+|\d+)"
    r"(?:\.(?P<frac>\d+))?"
    r"(?P<paren_close>\))?"
    r"\s?"
    r"(?P<scale>%|percent|billion|million|thousand|bn|mn|k\b)?",
    re.IGNORECASE,
)

_CITATION_MARKER_RE = re.compile(r"\[(\d+)\]")


@dataclass(frozen=True, slots=True)
class _ParsedNumber:
    raw_text: str
    raw_value: float  # digits exactly as written (sign-applied), no scale multiplier
    scaled_value: float  # raw_value * scale multiplier (== raw_value when no scale word)
    has_scale_signal: bool  # $ / % / comma-thousands / decimal / scale-word present


@dataclass(frozen=True, slots=True)
class NumericClaimResult:
    """One numeric claim found in the answer, attributed to one citation,
    with the verdict on whether it checks out against that citation's
    source content."""

    claim_text: str
    citation_index: int  # 0 is a sentinel for "no citation marker at all" -- see verify_answer
    verified: bool
    source_excerpt: str | None  # populated only when NOT verified, for debugging/display


def _parse_numbers(text: str) -> list[_ParsedNumber]:
    parsed: list[_ParsedNumber] = []
    for match in _NUMERIC_RE.finditer(text):
        int_part = match.group("int")
        frac_part = match.group("frac")
        digits = int_part.replace(",", "")
        value = float(f"{digits}.{frac_part}" if frac_part else digits)
        if match.group("sign") or (match.group("paren_open") and match.group("paren_close")):
            value = -value
        scale = (match.group("scale") or "").lower()
        multiplier = _SCALE_MULTIPLIERS.get(scale, 1.0)
        has_signal = bool(match.group("dollar") or frac_part or scale or "," in int_part)
        parsed.append(
            _ParsedNumber(
                raw_text=match.group(0).strip(),
                raw_value=value,
                scaled_value=value * multiplier,
                has_scale_signal=has_signal,
            )
        )
    return parsed


def _source_text(chunk: RetrievedChunk) -> str:
    """Everything a claim citing this chunk could legitimately be drawn
    from. For a `TABLE` chunk this is the *complete* structured table
    (`table_data`, joined from `TableData.raw_table_json`) -- deliberately
    NOT `chunk.content`, which for table chunks holds only a truncated
    (5-sample-row) embedding-summary string (see `table_chunker.py`'s
    `_embedding_text` docstring). Verifying against the truncated summary
    would falsely flag a correct number drawn from row 6+ as unsupported.
    """
    if chunk.table_data is None:
        return chunk.content
    headers = chunk.table_data.get("headers", [])
    rows = chunk.table_data.get("rows", [])
    header_line = " ".join(str(h) for h in headers)
    row_lines = "\n".join(" ".join(str(cell) for cell in row) for row in rows)
    return f"{chunk.content}\n{header_line}\n{row_lines}"


def _matches(claim: _ParsedNumber, source_numbers: list[_ParsedNumber]) -> bool:
    """Checks the claim's value against a source number under all four
    raw/scaled combinations, not just a direct equality -- financial
    prose and financial tables don't use the same scale convention for
    the "same" figure. A table cell under a "Revenue ($B)" header might
    just say `18.4`; the generated answer might say "$18.4 billion" or,
    just as validly, "$18,400 million." Comparing only
    claim.scaled_value == source.scaled_value would wrongly fail the
    first case (source has no scale word to multiply by); comparing only
    raw values would wrongly fail the second. Trying every combination is
    the honest way to say "these are the same number," independent of
    which side happened to spell out the scale.
    """
    for source in source_numbers:
        if (
            math.isclose(claim.raw_value, source.raw_value, rel_tol=0.02, abs_tol=0.05)
            or math.isclose(claim.scaled_value, source.raw_value, rel_tol=0.02, abs_tol=0.05)
            or math.isclose(claim.raw_value, source.scaled_value, rel_tol=0.02, abs_tol=0.05)
            or math.isclose(claim.scaled_value, source.scaled_value, rel_tol=0.02, abs_tol=0.05)
        ):
            return True
    return False


def verify_answer(answer_text: str, chunks: list[RetrievedChunk]) -> list[NumericClaimResult]:
    """Walks `answer_text` for `[n]` citation markers; for the text
    immediately preceding each marker (the claim `answer_generator.py`'s
    prompt instructs the model to place the marker directly after), pulls
    out every number that looks like an actual financial figure (has a
    `$`, `%`, decimal point, comma-thousands separator, or a scale word --
    see `_ParsedNumber.has_scale_signal`) and checks it against citation
    `n`'s source content. Bare small integers ("4 quarters," "2024") are
    not treated as claims needing verification -- they're not the kind of
    figure this project's numeric-traceability guarantee is about, and
    flagging them would just be noise.

    A marker whose index isn't in range of `chunks` (shouldn't happen --
    `answer_generator.py` only ever numbers the chunks it was actually
    given -- but a model can still emit an out-of-range number) is
    skipped, not treated as an automatic failure; there's nothing to
    verify a claim against if the citation itself doesn't resolve.

    **Text after the last citation marker (or the entire answer, if it
    has none at all) is scanned too, and is always recorded as
    unverified (`citation_index=0`, a sentinel -- there's no real
    citation to attach it to).** A model that states a figure and cites
    it correctly, then adds an uncited derived clause afterward (e.g.
    "... $171.3M [1]. That's up from $120.4M [1], an increase of $50.9M."
    -- the $50.9M is arithmetic the model did itself, never restated from
    a source, and is never followed by its own `[n]`) would otherwise
    have that number pass through completely unchecked: the window-per-
    marker loop only ever looks *before* a marker, so a claim with no
    marker after it was previously invisible to this function entirely,
    not just unverified. An unattributed numeric claim can't be verified
    by construction, so treating it as an automatic failure -- not
    silently skipping it -- is what actually keeps this project's
    numeric-traceability guarantee honest for text a real LLM produces
    (caught live this phase; see `docs/DECISIONS_LOG.md`).
    """
    results: list[NumericClaimResult] = []
    cited_chunks = {index + 1: chunk for index, chunk in enumerate(chunks)}

    cursor = 0
    for marker in _CITATION_MARKER_RE.finditer(answer_text):
        window = answer_text[cursor : marker.start()]
        cursor = marker.end()
        citation_index = int(marker.group(1))
        chunk = cited_chunks.get(citation_index)
        if chunk is None:
            continue

        source_numbers = _parse_numbers(_source_text(chunk))
        for claim in _parse_numbers(window):
            if not claim.has_scale_signal:
                continue
            verified = _matches(claim, source_numbers)
            results.append(
                NumericClaimResult(
                    claim_text=claim.raw_text,
                    citation_index=citation_index,
                    verified=verified,
                    source_excerpt=None if verified else _source_text(chunk)[:280],
                )
            )

    for claim in _parse_numbers(answer_text[cursor:]):
        if not claim.has_scale_signal:
            continue
        results.append(
            NumericClaimResult(
                claim_text=claim.raw_text,
                citation_index=0,
                verified=False,
                source_excerpt="(no citation marker follows this claim)",
            )
        )

    return results
