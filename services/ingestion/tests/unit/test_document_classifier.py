"""document_classifier.py's heuristic filing/transcript/deck scoring, on
synthetic `ParsedDocument` fixtures built with just enough sample text to
trip each kind's patterns."""
from __future__ import annotations

from src.parsing.document_classifier import (
    DocumentKind,
    classify_document,
    matches_declared_type,
)
from src.parsing.pdf_parser import ParsedDocument, ParsedPage


def _doc(*page_texts: str) -> ParsedDocument:
    pages = [
        ParsedPage(page_number=i + 1, width=612.0, height=792.0, raw_text=text, lines=[], table_bboxes=[])
        for i, text in enumerate(page_texts)
    ]
    return ParsedDocument(source_path=__file__, page_count=len(pages), pages=pages)  # type: ignore[arg-type]


def test_classifies_a_10k_style_filing() -> None:
    text = (
        "UNITED STATES SECURITIES AND EXCHANGE COMMISSION\n"
        "Washington, D.C. 20549\nForm 10-K\nPART I\nItem 1. Business\n"
        "For the fiscal year ended December 31, 2025.\n" + ("Operating results discussion. " * 50)
    )
    result = classify_document(_doc(text))
    assert result.kind == DocumentKind.FILING
    assert result.confidence > 0.0


def test_classifies_an_earnings_call_transcript() -> None:
    text = (
        "Q4 2025 Earnings Call\nOperator:\nGood afternoon and welcome to the earnings call.\n"
        "Question-and-Answer Session\n[Operator Instructions]\n"
        + ("Thank you for the question. " * 50)
    )
    result = classify_document(_doc(text))
    assert result.kind == DocumentKind.TRANSCRIPT


def test_classifies_a_sparse_investor_deck() -> None:
    # Sparse per-page text + deck-specific phrasing, no filing/transcript signals.
    pages = ["Q4 2025 Investor Presentation", "Forward-Looking Statements", "Non-GAAP Reconciliation"]
    result = classify_document(_doc(*pages))
    assert result.kind == DocumentKind.DECK


def test_unknown_when_no_signals_present() -> None:
    result = classify_document(_doc("", "", ""))
    assert result.kind == DocumentKind.UNKNOWN
    assert result.confidence == 0.0


def test_matches_declared_type() -> None:
    assert matches_declared_type(DocumentKind.FILING, "form_10k") is True
    assert matches_declared_type(DocumentKind.FILING, "form_10q") is True
    assert matches_declared_type(DocumentKind.FILING, "earnings_transcript") is False
    assert matches_declared_type(DocumentKind.UNKNOWN, "investor_deck") is True
