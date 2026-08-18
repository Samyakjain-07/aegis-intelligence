"""`GET /admin/analytics`, `GET /admin/flagged-answers` -- real
implementations backing two of `docs/architecture.md` §8's Admin use cases
("View analytics dashboard", "Review flagged answers"). "Manage org
users" and "Configure retention & access" have no route yet -- out of
scope for this phase's surface, left for whichever later phase implements
org/user management.

**Tenant scoping:** `Conversation`/`Query`/`Answer`/`EvalResult` rows are
scoped by `tenant.org_id` (via each `Conversation`'s owning `User`) --
those tables genuinely belong to an organization in the ER model.
`Document`/`Company` counts are deliberately NOT scoped, mirroring
`documents.py`'s Phase 4 precedent: the filing corpus is shared reference
data (public SEC filings), not tenant-owned. Real role-based authorization
(admin-only access to this router) isn't enforced yet either --
`tenant.role` is always `None` until real auth exists (see `deps.py`), so
there's nothing meaningful to check against yet.

**"Flagged" is one OR of two independent signals**, computed the same way
in both routes below (`_flagged_condition`): `Answer.confidence_score`
below the same `LOW_CONFIDENCE_THRESHOLD` the live query pipeline itself
uses to set `low_confidence` (`core/confidence_scorer.py`), OR a linked
`EvalResult.flagged_by_human = True`. `EvalResult` rows don't exist yet
(Phase 8's eval harness, not yet built, is the only writer) -- so today
every flagged row reaches these endpoints via the confidence path. The
human-review path is still wired in now rather than bolted on later,
since the query/filter shape doesn't need to change once Phase 8 starts
writing `EvalResult` rows.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import ColumnElement, Date, case, cast, func, or_, select
from sqlalchemy.orm import Session

from src.api.v1.deps import TenantContext, get_db, get_tenant_context
from src.core.confidence_scorer import LOW_CONFIDENCE_THRESHOLD
from src.models.db.answer import Answer
from src.models.db.citation import Citation
from src.models.db.company import Company
from src.models.db.conversation import Conversation
from src.models.db.document import Document
from src.models.db.document_chunk import DocumentChunk
from src.models.db.enums import DocumentStatus
from src.models.db.eval_result import EvalResult
from src.models.db.query import Query as QueryRow
from src.models.db.user import User
from src.models.schemas.admin import (
    AdminAnalyticsResponse,
    FlaggedAnswerResponse,
    FlaggedAnswersListResponse,
    QueryVolumeDayResponse,
    TickerCitationCountResponse,
)

router = APIRouter(prefix="/admin", tags=["admin"])

_QUERY_VOLUME_WINDOW_DAYS = 7
_TOP_CITED_TICKERS_LIMIT = 5
_DEFAULT_FLAGGED_ANSWERS_LIMIT = 50


def _flagged_condition() -> ColumnElement[bool]:
    """The one flagged-or-not predicate every query below shares -- see
    module docstring. Requires `Answer` and `EvalResult` to already be
    joined (an `outerjoin` on `EvalResult`, since most queries have none
    yet) in whatever statement uses this."""
    return or_(
        Answer.confidence_score < LOW_CONFIDENCE_THRESHOLD,
        EvalResult.flagged_by_human.is_(True),
    )


def _flag_reason(answer: Answer, eval_result: EvalResult | None) -> str:
    """Human-readable reason(s) a specific `Answer` matched
    `_flagged_condition()` -- both can be true at once, so this is a list,
    not an either/or."""
    reasons: list[str] = []
    if answer.confidence_score < LOW_CONFIDENCE_THRESHOLD:
        reasons.append(
            f"Low confidence ({answer.confidence_score:.2f} < {LOW_CONFIDENCE_THRESHOLD:.2f})"
        )
    if eval_result is not None and eval_result.flagged_by_human:
        reasons.append("Flagged by human reviewer")
    return "; ".join(reasons) if reasons else "Flagged"


@router.get("/analytics", response_model=AdminAnalyticsResponse)
def get_analytics(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
) -> AdminAnalyticsResponse:
    """Real KPI counters + the last `_QUERY_VOLUME_WINDOW_DAYS` days of
    query/flagged volume + the most-cited companies, replacing Phase 3's
    all-zero placeholder. See module docstring for the tenant-scoping and
    flagged-condition rules shared with `list_flagged_answers` below."""
    total_documents = db.execute(select(func.count(Document.document_id))).scalar_one()
    indexed_document_count = db.execute(
        select(func.count(Document.document_id)).where(Document.status == DocumentStatus.COMPLETED)
    ).scalar_one()

    total_conversations = db.execute(
        select(func.count(Conversation.conversation_id))
        .join(User, User.user_id == Conversation.user_id)
        .where(User.org_id == tenant.org_id)
    ).scalar_one()
    active_analyst_count = db.execute(
        select(func.count(func.distinct(Conversation.user_id)))
        .join(User, User.user_id == Conversation.user_id)
        .where(User.org_id == tenant.org_id)
    ).scalar_one()

    flagged_expr = _flagged_condition()
    total_queries, average_confidence_score, flagged_answer_count = db.execute(
        select(
            func.count(func.distinct(QueryRow.query_id)),
            func.avg(Answer.confidence_score),
            func.count(func.distinct(case((flagged_expr, Answer.answer_id)))),
        )
        .select_from(QueryRow)
        .join(Conversation, Conversation.conversation_id == QueryRow.conversation_id)
        .join(User, User.user_id == Conversation.user_id)
        .outerjoin(Answer, Answer.query_id == QueryRow.query_id)
        .outerjoin(EvalResult, EvalResult.query_id == QueryRow.query_id)
        .where(User.org_id == tenant.org_id)
    ).one()
    low_confidence_rate = flagged_answer_count / total_queries if total_queries else None

    window_start_date = (
        datetime.now(timezone.utc) - timedelta(days=_QUERY_VOLUME_WINDOW_DAYS - 1)
    ).date()
    day_col = cast(QueryRow.created_at, Date)
    volume_rows = db.execute(
        select(
            day_col.label("day"),
            func.count(func.distinct(QueryRow.query_id)).label("query_count"),
            func.count(func.distinct(case((flagged_expr, QueryRow.query_id)))).label("flagged_count"),
        )
        .select_from(QueryRow)
        .join(Conversation, Conversation.conversation_id == QueryRow.conversation_id)
        .join(User, User.user_id == Conversation.user_id)
        .outerjoin(Answer, Answer.query_id == QueryRow.query_id)
        .outerjoin(EvalResult, EvalResult.query_id == QueryRow.query_id)
        .where(User.org_id == tenant.org_id, day_col >= window_start_date)
        .group_by(day_col)
    ).all()
    counts_by_day: dict[date, tuple[int, int]] = {
        row.day: (row.query_count, row.flagged_count) for row in volume_rows
    }
    # Always _QUERY_VOLUME_WINDOW_DAYS entries, oldest first, zero-filled
    # for days with no queries -- so the chart always renders a full
    # 7-point series instead of gaps on quiet days.
    query_volume_last_7_days = [
        QueryVolumeDayResponse(
            date=day.isoformat(),
            query_count=counts_by_day.get(day, (0, 0))[0],
            flagged_count=counts_by_day.get(day, (0, 0))[1],
        )
        for day in (
            (datetime.now(timezone.utc) - timedelta(days=offset)).date()
            for offset in range(_QUERY_VOLUME_WINDOW_DAYS - 1, -1, -1)
        )
    ]

    citation_rows = db.execute(
        select(Company.ticker, func.count(Citation.citation_id).label("citation_count"))
        .select_from(Citation)
        .join(DocumentChunk, DocumentChunk.chunk_id == Citation.chunk_id)
        .join(Document, Document.document_id == DocumentChunk.document_id)
        .join(Company, Company.company_id == Document.company_id)
        .join(Answer, Answer.answer_id == Citation.answer_id)
        .join(QueryRow, QueryRow.query_id == Answer.query_id)
        .join(Conversation, Conversation.conversation_id == QueryRow.conversation_id)
        .join(User, User.user_id == Conversation.user_id)
        .where(User.org_id == tenant.org_id)
        .group_by(Company.ticker)
        .order_by(func.count(Citation.citation_id).desc())
        .limit(_TOP_CITED_TICKERS_LIMIT)
    ).all()
    max_citation_count = citation_rows[0].citation_count if citation_rows else 0
    top_cited_tickers = [
        TickerCitationCountResponse(
            ticker=row.ticker,
            citation_count=row.citation_count,
            percent_of_max=(
                round(100.0 * row.citation_count / max_citation_count, 1) if max_citation_count else 0.0
            ),
        )
        for row in citation_rows
    ]

    return AdminAnalyticsResponse(
        total_documents=total_documents,
        indexed_document_count=indexed_document_count,
        total_conversations=total_conversations,
        total_queries=total_queries,
        average_confidence_score=(
            round(average_confidence_score, 4) if average_confidence_score is not None else None
        ),
        flagged_answer_count=flagged_answer_count,
        low_confidence_rate=(
            round(low_confidence_rate, 4) if low_confidence_rate is not None else None
        ),
        active_analyst_count=active_analyst_count,
        query_volume_last_7_days=query_volume_last_7_days,
        top_cited_tickers=top_cited_tickers,
    )


@router.get("/flagged-answers", response_model=FlaggedAnswersListResponse)
def list_flagged_answers(
    limit: int = Query(default=_DEFAULT_FLAGGED_ANSWERS_LIMIT, ge=1, le=200),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
) -> FlaggedAnswersListResponse:
    """Real `Answer` rows matching `_flagged_condition()`, newest first,
    scoped by `tenant.org_id`. Replaces Phase 3's always-empty
    placeholder."""
    flagged_expr = _flagged_condition()

    def _joined_query():  # local helper: identical join chain for both the count and the page below
        return (
            select(Answer, QueryRow, User, EvalResult)
            .select_from(Answer)
            .join(QueryRow, QueryRow.query_id == Answer.query_id)
            .join(Conversation, Conversation.conversation_id == QueryRow.conversation_id)
            .join(User, User.user_id == Conversation.user_id)
            .outerjoin(EvalResult, EvalResult.query_id == QueryRow.query_id)
            .where(User.org_id == tenant.org_id, flagged_expr)
        )

    total = db.execute(
        select(func.count()).select_from(_joined_query().subquery())
    ).scalar_one()

    rows = db.execute(_joined_query().order_by(Answer.generated_at.desc()).limit(limit)).all()

    flagged_answers = [
        FlaggedAnswerResponse(
            answer_id=answer.answer_id,
            query_id=query_row.query_id,
            conversation_id=query_row.conversation_id,
            user_email=user.email,
            query_text=query_row.query_text,
            answer_text=answer.answer_text,
            confidence_score=answer.confidence_score,
            flag_reason=_flag_reason(answer, eval_result),
            generated_at=answer.generated_at,
        )
        for answer, query_row, user, eval_result in rows
    ]
    return FlaggedAnswersListResponse(flagged_answers=flagged_answers, total=total)
