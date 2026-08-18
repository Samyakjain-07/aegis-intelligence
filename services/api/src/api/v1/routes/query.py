"""`POST /query`, `POST /query/followup` -- the real query pipeline
(`docs/architecture.md` §1 Pipeline B), replacing Phase 3's stubs.

Both routes funnel into `_handle_query`, which is the same for a fresh
question and a follow-up once each has resolved *what question to
actually retrieve against* -- `submit_query` uses the raw `query_text`
unchanged (per `QueryRequest`'s docstring: passing an existing
`conversation_id` attaches the question to a thread without invoking
follow-up reformulation), `submit_followup_query` first runs it through
`history_manager.reformulate_followup`. The pipeline itself doesn't care
which path it came from.

Pipeline, in order: `multi_query.expand_query` -> `hybrid_retriever.retrieve`
(BM25 + dense in parallel per variant, RRF-fused) -> `reranker.rerank`
(Cohere) -> `confidence_scorer.retrieval_confidence` (pre-generation
signal) -> `answer_generator.generate_answer` (grounded, or the
extractive fallback) -> `numeric_verifier.verify_answer` (every numeric
claim checked against its cited chunk) -> `confidence_scorer.score_final`
(numeric verification can only ever lower confidence, never raise it) ->
`citation_resolver` (per actually-cited chunk: `SourceLocation` + a
display snippet) -> persist `Query`/`Answer`/`Citation` rows -> respond.

**No separate "is retrieval confident enough to even generate?" gate**
(`docs/architecture.md` §3 frames this as a pre-generation branch):
`answer_generator.generate_answer([])` already returns a safe "not enough
information" message when `reranked` is empty, which is the one case
worth gating on -- an arbitrary numeric threshold between "clearly
irrelevant" and "borderline" isn't something to hardcode without eval
data to calibrate it against (Phase 8's job), so the post-generation
`confidence_score`/`low_confidence` signal is what actually communicates
"treat this answer cautiously" instead.
"""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from src.api.v1.deps import (
    TenantContext,
    get_db,
    get_or_create_actor,
    get_tenant_context,
)
from src.core import (
    answer_generator,
    citation_resolver,
    confidence_scorer,
    history_manager,
    hybrid_retriever,
    multi_query,
    numeric_verifier,
    reranker,
)
from src.core.types import RetrievedChunk
from src.models.db.answer import Answer
from src.models.db.citation import Citation
from src.models.db.conversation import Conversation
from src.models.db.query import Query
from src.models.schemas.citation import CitationResponse
from src.models.schemas.query import FollowupQueryRequest, QueryRequest, QueryResponse
from src.observability.metrics import StageTimer

router = APIRouter(prefix="/query", tags=["query"])

# Fused candidates handed to the reranker, and how many of the reranked
# results are actually offered to answer_generator.py as context. Picked
# by inspection (a typical analyst question is answerable from 3-6 chunks;
# 20 candidates gives the reranker enough real choices without an
# oversized Cohere rerank call) -- not tuned against Phase 8's eval
# harness yet, which is the right place to revisit these once it exists.
_RETRIEVE_TOP_N = 20
_RERANK_TOP_N = 6

_CITATION_MARKER_RE = re.compile(r"\[(\d+)\]")


def _extract_cited_indices(answer_text: str, max_index: int) -> list[int]:
    """Which context positions (`[1]`, `[2]`, ...) the generated answer
    actually referenced, in the order they first appear. A `Citation` row
    is persisted only for chunks the answer text actually cites -- not for
    every chunk `reranker.py` offered as context but the model (or the
    extractive fallback) never used; `_RERANK_TOP_N` is deliberately
    larger than what a typical answer ends up citing.
    """
    seen: dict[int, None] = {}
    for match in _CITATION_MARKER_RE.finditer(answer_text):
        index = int(match.group(1))
        if 1 <= index <= max_index:
            seen.setdefault(index, None)
    return list(seen.keys())


def _renumber_markers(answer_text: str, renumbering: dict[int, int]) -> str:
    """Rewrites `[n]` markers so they're contiguous (`1, 2, 3, ...`) and
    line up positionally with the `citations` list in the response.

    Without this, a marker number is only meaningful relative to
    `reranker.py`'s full candidate list (up to `_RERANK_TOP_N` of them),
    but `citations` only contains the subset that was *actually* cited --
    if the model cites `[1]` and `[4]` and skips the rest, `citations`
    would have two entries while the text still says "[4]," and a
    frontend indexing `citations[3]` to resolve it would be wrong (or
    out of range). Rewriting the text so those become `[1]` and `[2]`
    means `citations[i]` always corresponds to the `(i+1)`-th marker as it
    literally appears in the (rewritten) text -- no separate index field
    needed on `CitationResponse` for the frontend to resolve a click.

    A marker whose original index has no entry in `renumbering` (out of
    range, or the model cited a position that didn't survive into
    `cited_indices`) is left exactly as-is -- there's nothing to renumber
    it to, and leaving it alone is more honest than silently dropping it.
    """

    def _replace(match: re.Match[str]) -> str:
        new_index = renumbering.get(int(match.group(1)))
        return f"[{new_index}]" if new_index is not None else match.group(0)

    return _CITATION_MARKER_RE.sub(_replace, answer_text)


def _handle_query(
    db: Session,
    conversation: Conversation,
    *,
    raw_query_text: str,
    retrieval_query_text: str,
    reformulated_query_text: str | None,
) -> QueryResponse:
    """Shared body for both routes -- see module docstring for the
    pipeline order. `raw_query_text` is what gets stored as
    `Query.query_text` (what the analyst actually typed);
    `retrieval_query_text` is what actually drives retrieval/generation
    (identical to `raw_query_text` for a fresh question, the
    history-reformulated version for a follow-up).

    Timed stage-by-stage via `StageTimer` (Phase 8, `observability/
    metrics.py`) -- `timer.log_summary()` at the bottom emits one
    structured log line per request with each stage's latency, the
    "latency" metric `PROJECT_HANDBOOK.md` §6 Phase 8 names; LangSmith
    tracing (`observability/tracing.py`, applied directly to each `core/`
    function below) is the richer per-stage view when configured, this is
    the always-on floor under it.
    """
    timer = StageTimer()
    with timer.stage("multi_query"):
        expanded_queries = multi_query.expand_query(retrieval_query_text)
    with timer.stage("retrieval"):
        candidates = hybrid_retriever.retrieve(db, expanded_queries, top_n=_RETRIEVE_TOP_N)
    with timer.stage("rerank"):
        reranked = reranker.rerank(retrieval_query_text, candidates, top_n=_RERANK_TOP_N)

    retrieval_conf = confidence_scorer.retrieval_confidence(reranked)
    with timer.stage("generation"):
        generated = answer_generator.generate_answer(retrieval_query_text, reranked)
    # Numeric verification runs against generated.answer_text's *original*
    # marker numbers (matching reranked's positions 1:1) -- it never
    # touches the database and doesn't care whether those numbers end up
    # contiguous, so there's no need to wait for the renumbering below.
    with timer.stage("numeric_verification"):
        numeric_results = numeric_verifier.verify_answer(generated.answer_text, reranked)
    final_confidence = confidence_scorer.score_final(retrieval_conf, numeric_results)

    # Renumber [n] markers to be contiguous and line up positionally with
    # `citations` below -- see _renumber_markers's docstring for why this
    # has to happen before anything is persisted (Answer.answer_text is
    # the renumbered version, not generated.answer_text verbatim).
    cited_indices = _extract_cited_indices(generated.answer_text, len(reranked))
    renumbering = {old_index: new_index for new_index, old_index in enumerate(cited_indices, start=1)}
    answer_text = _renumber_markers(generated.answer_text, renumbering)

    query_row = Query(
        conversation_id=conversation.conversation_id,
        query_text=raw_query_text,
        reformulated_query_text=reformulated_query_text,
    )
    db.add(query_row)
    db.flush()  # assigns query_row.query_id for the Answer FK below

    answer_row = Answer(
        query_id=query_row.query_id,
        answer_text=answer_text,
        confidence_score=final_confidence.confidence_score,
    )
    db.add(answer_row)
    db.flush()  # assigns answer_row.answer_id for the Citation rows below

    citation_rows: list[tuple[Citation, RetrievedChunk]] = []
    for index in cited_indices:
        chunk = reranked[index - 1]
        location = citation_resolver.resolve_source_location(chunk)
        citation_row = Citation(
            answer_id=answer_row.answer_id,
            chunk_id=chunk.chunk_id,
            exact_location=location.exact_location(),
            snippet=citation_resolver.build_snippet(chunk),
        )
        db.add(citation_row)
        citation_rows.append((citation_row, chunk))
    db.flush()  # assigns citation_id on each row for the response below

    citations = [
        CitationResponse(
            citation_id=row.citation_id,
            answer_id=row.answer_id,
            chunk_id=row.chunk_id,
            exact_location=row.exact_location,
            snippet=row.snippet,
            document_title=chunk.document_title,
            document_type=chunk.document_type,
            ticker=chunk.ticker,
            page_number=chunk.page_number,
            fiscal_year=chunk.fiscal_year,
            fiscal_quarter=chunk.fiscal_quarter,
        )
        for row, chunk in citation_rows
    ]

    db.commit()
    db.refresh(query_row)

    timer.log_summary(
        query_id=query_row.query_id,
        confidence_score=final_confidence.confidence_score,
        citation_count=len(citations),
    )

    return QueryResponse(
        query_id=query_row.query_id,
        conversation_id=conversation.conversation_id,
        query_text=raw_query_text,
        reformulated_query_text=reformulated_query_text,
        answer_text=answer_text,
        confidence_score=final_confidence.confidence_score,
        low_confidence=final_confidence.low_confidence,
        citations=citations,
        created_at=query_row.created_at,
    )


@router.post("", response_model=QueryResponse)
def submit_query(
    body: QueryRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
) -> QueryResponse:
    """A fresh question. Omitting `conversation_id` starts a new
    `Conversation`; passing one attaches the question to an existing
    thread -- without follow-up reformulation, per `QueryRequest`'s
    docstring (that's what `/query/followup` is for).
    """
    actor = get_or_create_actor(db, tenant)

    if body.conversation_id is not None:
        conversation = db.get(Conversation, body.conversation_id)
        if conversation is None or conversation.user_id != actor.user_id:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND, detail="Conversation not found."
            )
    else:
        conversation = Conversation(user_id=actor.user_id)
        db.add(conversation)
        db.flush()  # assigns conversation.conversation_id for the Query FK

    return _handle_query(
        db,
        conversation,
        raw_query_text=body.query_text,
        retrieval_query_text=body.query_text,
        reformulated_query_text=None,
    )


@router.post("/followup", response_model=QueryResponse)
def submit_followup_query(
    body: FollowupQueryRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
) -> QueryResponse:
    """A follow-up question inside an existing `Conversation`. Reads the
    conversation's prior turns, reformulates `query_text` into a
    self-contained question via `history_manager.py`, then runs the same
    pipeline `submit_query` does against the reformulated text.
    """
    actor = get_or_create_actor(db, tenant)

    conversation = (
        db.execute(
            select(Conversation)
            .where(Conversation.conversation_id == body.conversation_id)
            .options(selectinload(Conversation.queries).joinedload(Query.answer))
        )
        .unique()
        .scalar_one_or_none()
    )
    if conversation is None or conversation.user_id != actor.user_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Conversation not found."
        )

    prior_turns = [
        (prior_query.query_text, prior_query.answer.answer_text)
        for prior_query in conversation.queries
        if prior_query.answer is not None
    ]
    reformulated = history_manager.reformulate_followup(prior_turns, body.query_text)
    reformulated_query_text = reformulated if reformulated != body.query_text else None

    return _handle_query(
        db,
        conversation,
        raw_query_text=body.query_text,
        retrieval_query_text=reformulated,
        reformulated_query_text=reformulated_query_text,
    )
