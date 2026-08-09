"""Classifies a parsed PDF's *content* as a filing, transcript, or deck --
`docs/architecture.md` §1 step 2, and the `P2` decision diamond in that
doc's ingestion flowchart ("Filing, transcript, or deck?").

This is independent of `Document.document_type` (the enum the analyst
already picked in the Phase 4 upload form -- `FORM_10K`/`FORM_10Q`/
`EARNINGS_TRANSCRIPT`/`INVESTOR_DECK`): that field says what the uploader
*claims* the file is; this module says what the file's actual text
*looks like*, purely from content signals. The two should usually agree;
`tasks/ingest_document.py` logs both so a mismatch is visible without
this module needing to know about (or import) the API's enum. Pure
heuristics, no LLM -- unlike `chunking/agentic_chunker.py`, nothing in
`PROJECT_HANDBOOK.md`'s Phase 5 prompt calls this stage "LLM-assisted",
and a three-way document-shape classification is squarely the kind of
thing regex/keyword scoring handles reliably and for free.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from src.parsing.pdf_parser import ParsedDocument

# How many leading pages to sample -- SEC filings/transcripts/decks all
# reveal their shape in the first handful of pages (cover page, table of
# contents, first speaker turn), and sampling avoids paying classification
# cost proportional to a 200-page 10-K.
_SAMPLE_PAGE_COUNT = 5

# Below this word-count-per-sampled-page average, treat "sparse text" as a
# deck signal (slide decks are image/bullet-heavy, not dense paragraphs).
_DECK_WORDS_PER_PAGE_THRESHOLD = 100.0


class DocumentKind(str, Enum):
    FILING = "filing"
    TRANSCRIPT = "transcript"
    DECK = "deck"
    UNKNOWN = "unknown"


# Maps a content-classified DocumentKind to the `Document.document_type`
# string value(s) (the API-side `DocumentType` enum's values -- not
# imported directly, see this module's docstring on why this file stays
# independent of the API's models) it should agree with. Used by
# `tasks/ingest_document.py` to log a mismatch, not to overrule the
# analyst's own upload-time selection.
_EXPECTED_DOCUMENT_TYPES: dict[DocumentKind, frozenset[str]] = {
    DocumentKind.FILING: frozenset({"form_10k", "form_10q"}),
    DocumentKind.TRANSCRIPT: frozenset({"earnings_transcript"}),
    DocumentKind.DECK: frozenset({"investor_deck"}),
    DocumentKind.UNKNOWN: frozenset(),
}


def matches_declared_type(kind: DocumentKind, document_type: str) -> bool:
    """`True` if the content-classified `kind` is consistent with the
    `Document.document_type` the analyst picked at upload time. Always
    `True` for `UNKNOWN` -- there's nothing confident enough to disagree
    with, so it shouldn't be reported as a mismatch."""
    if kind is DocumentKind.UNKNOWN:
        return True
    return document_type in _EXPECTED_DOCUMENT_TYPES[kind]


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    kind: DocumentKind
    confidence: float  # 0.0-1.0, the winning kind's normalized signal score
    signals: list[str]  # human-readable, for the log line in ingest_document.py


_FILING_PATTERNS = [
    re.compile(r"\bPART\s+[IVX]+\b"),
    re.compile(r"\bItem\s+\d+[A-Z]?\.", re.IGNORECASE),
    re.compile(r"SECURITIES AND EXCHANGE COMMISSION", re.IGNORECASE),
    re.compile(r"\bForm\s+10-[KQ]\b", re.IGNORECASE),
    re.compile(r"\bfiscal year ended\b", re.IGNORECASE),
]

_TRANSCRIPT_PATTERNS = [
    re.compile(r"^\s*Operator:?\s*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"\bQuestion-and-Answer\b", re.IGNORECASE),
    re.compile(r"\bearnings call\b", re.IGNORECASE),
    re.compile(r"^\s*[A-Z][\w.'-]+(?: [A-Z][\w.'-]+){1,3}\s*[-–]\s*[A-Za-z&,.' ]+\s*$", re.MULTILINE),
    re.compile(r"\[(?:Operator Instructions|indiscernible|inaudible)\]", re.IGNORECASE),
]

_DECK_PATTERNS = [
    re.compile(r"\bforward[- ]looking statements\b", re.IGNORECASE),
    re.compile(r"\binvestor (presentation|day|deck)\b", re.IGNORECASE),
    re.compile(r"\bnon-GAAP\b", re.IGNORECASE),
]


def _score(text: str, patterns: list[re.Pattern[str]]) -> tuple[int, list[str]]:
    hits: list[str] = []
    for pattern in patterns:
        if pattern.search(text):
            hits.append(pattern.pattern)
    return len(hits), hits


def classify_document(parsed: ParsedDocument) -> ClassificationResult:
    sample_pages = parsed.pages[:_SAMPLE_PAGE_COUNT]
    sample_text = "\n".join(p.raw_text for p in sample_pages)

    filing_score, filing_hits = _score(sample_text, _FILING_PATTERNS)
    transcript_score, transcript_hits = _score(sample_text, _TRANSCRIPT_PATTERNS)
    deck_score, deck_hits = _score(sample_text, _DECK_PATTERNS)

    words_per_page = (
        (len(sample_text.split()) / len(sample_pages)) if sample_pages else 0.0
    )
    signals = [f"filing:{filing_hits}", f"transcript:{transcript_hits}", f"deck:{deck_hits}"]
    # Guarded on non-empty sample text: an empty/unparseable document has
    # 0 words/page too, but that's absence of evidence, not evidence of a
    # sparse slide deck -- it should fall through to UNKNOWN below, not
    # get misclassified as DECK.
    if sample_text.strip() and words_per_page < _DECK_WORDS_PER_PAGE_THRESHOLD:
        deck_score += 1
        signals.append(f"deck:sparse_text({words_per_page:.0f} words/page)")

    scores = {
        DocumentKind.FILING: filing_score,
        DocumentKind.TRANSCRIPT: transcript_score,
        DocumentKind.DECK: deck_score,
    }
    total = sum(scores.values())
    if total == 0:
        return ClassificationResult(kind=DocumentKind.UNKNOWN, confidence=0.0, signals=signals)

    winner = max(scores, key=lambda k: scores[k])
    confidence = scores[winner] / total
    return ClassificationResult(kind=winner, confidence=confidence, signals=signals)
