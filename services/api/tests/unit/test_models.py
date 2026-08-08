"""Unit tests for the Phase 2 SQLAlchemy models.

Deliberately narrow -- this isn't CRUD coverage for all 11 entities. It
targets three specific constraint/relationship behaviors that earlier
`docs/DECISIONS_LOG.md` entries called out as load-bearing design
decisions, not incidental ORM behavior:

1. `DocumentChunk`'s composite uniqueness (`document_id`, `page_number`,
   `chunk_index`) -- the mechanism the idempotent-re-ingestion guarantee
   in `architecture.md` §2 depends on.
2. `Citation` actually resolving both of its FKs as usable ORM
   relationships -- the whole point of the entity.
3. `Citation.chunk_id`'s deliberately-missing `ondelete="CASCADE"` -- the
   audit-trail protection described in the `citation.py` decisions-log
   entry. This is the test that would catch a regression if someone
   "cleaned up" that FK to `CASCADE` later.

See the `docs/DECISIONS_LOG.md` entry for this file for the full reasoning
behind picking exactly these three.
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models.db import (
    Answer,
    ChunkType,
    Citation,
    Company,
    Conversation,
    Document,
    DocumentChunk,
    DocumentType,
    Organization,
    Query,
    User,
    UserRole,
)


def _make_document_chunk(
    session: Session, *, page_number: int = 1, chunk_index: int = 0
) -> DocumentChunk:
    """Builds the minimum graph a `DocumentChunk` needs to exist:
    `Company -> Document -> DocumentChunk`. Adding just the chunk to the
    session is enough -- the default "save-update" cascade on
    `relationship()` pulls the still-transient `document`/`company` along
    with it at flush time."""
    company = Company(
        ticker=f"T{uuid.uuid4().hex[:8].upper()}", name="Test Co", sector="Technology"
    )
    document = Document(
        company=company,
        document_type=DocumentType.FORM_10K,
        fiscal_year=2025,
        upload_date=date(2025, 1, 1),
        source_url="https://example.com/filing.pdf",
        title="Test 10-K FY2025",
    )
    chunk = DocumentChunk(
        document=document,
        chunk_type=ChunkType.NARRATIVE,
        content="Revenue grew 12% year over year.",
        page_number=page_number,
        chunk_index=chunk_index,
    )
    session.add(chunk)
    session.flush()
    return chunk


def _make_answer(session: Session) -> Answer:
    """Builds the minimum graph an `Answer` needs to exist:
    `Organization -> User -> Conversation -> Query -> Answer`."""
    org = Organization(name="Test Org")
    user = User(
        organization=org,
        name="Test Analyst",
        email=f"{uuid.uuid4().hex}@example.com",
        role=UserRole.ANALYST,
    )
    conversation = Conversation(user=user)
    query = Query(conversation=conversation, query_text="What was Q4 revenue?")
    answer = Answer(
        query=query, answer_text="Q4 revenue was $1.2B.", confidence_score=0.92
    )
    session.add(answer)
    session.flush()
    return answer


class TestDocumentChunkUniqueness:
    """`chunk_index` was added to `DocumentChunk` beyond the pasted ER
    diagram specifically to back this constraint -- see the
    `document_chunk.py` entry in `docs/DECISIONS_LOG.md`."""

    def test_duplicate_document_page_chunk_index_rejected(
        self, db_session: Session
    ) -> None:
        first = _make_document_chunk(db_session, page_number=3, chunk_index=0)

        duplicate = DocumentChunk(
            document_id=first.document_id,
            chunk_type=ChunkType.FOOTNOTE,
            content="A different chunk, same slot.",
            page_number=3,
            chunk_index=0,
        )
        db_session.add(duplicate)

        with pytest.raises(IntegrityError):
            db_session.flush()


class TestCitationRelationships:
    """A `Citation` that can't resolve back to both the `Answer` it
    supports and the `DocumentChunk` it cites isn't doing its job --
    that's the `source_location` concept from `architecture.md` §2/§3."""

    def test_citation_resolves_answer_and_chunk(self, db_session: Session) -> None:
        answer = _make_answer(db_session)
        chunk = _make_document_chunk(db_session)

        citation = Citation(
            answer=answer,
            chunk=chunk,
            exact_location="p.3, para 2",
            snippet="Revenue grew 12% year over year.",
        )
        db_session.add(citation)
        db_session.commit()

        db_session.expire_all()
        fetched = db_session.get(Citation, citation.citation_id)

        assert fetched is not None
        assert fetched.answer.answer_id == answer.answer_id
        assert fetched.chunk.chunk_id == chunk.chunk_id
        assert fetched in fetched.answer.citations
        assert fetched in fetched.chunk.citations


class TestCitationChunkForeignKeyIsProtective:
    """`Citation.chunk_id` deliberately has no `ondelete="CASCADE"` (see
    the `answer.py`/`citation.py`/`eval_result.py` decisions-log entry) --
    a chunk that's ever been cited must not be silently deletable out from
    under that citation."""

    def test_deleting_cited_chunk_is_blocked(self, db_session: Session) -> None:
        answer = _make_answer(db_session)
        chunk = _make_document_chunk(db_session)
        citation = Citation(
            answer=answer,
            chunk=chunk,
            exact_location="p.1",
            snippet="Some cited text.",
        )
        db_session.add(citation)
        db_session.commit()

        db_session.delete(chunk)

        with pytest.raises(IntegrityError):
            db_session.flush()
