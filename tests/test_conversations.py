"""Conversation service tests: CRUD, title derivation, ordering, audit exclusion.

Conversations are UI state for the AI command center, not writes to the
books, so they are kept out of the audit trail (``_SKIP`` in
``app/services/audit.py``). These tests exercise the service layer directly
and assert that no ``AuditLog`` rows are produced for ``ChatConversation``
operations.
"""

import datetime
import json

import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.models.audit import AuditLog
from app.services import conversations
from app.services.errors import NotFoundError


@pytest.fixture
def db(app_client):
    """A session against the fresh test database (tables already created)."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _messages(first: str) -> list[dict]:
    return [{"role": "user", "content": first}]


def test_create_derives_title_from_first_user_message(db) -> None:
    conv = conversations.create_conversation(
        db, messages=_messages("What's my cash balance?")
    )
    assert conv.title == "What's my cash balance?"
    assert json.loads(conv.messages_json) == _messages("What's my cash balance?")
    assert conv.last_done_json is None


def test_create_truncates_long_title(db) -> None:
    long_text = "word " * 30  # 150 chars, well over the 60-char cap
    conv = conversations.create_conversation(db, messages=_messages(long_text))
    assert conv.title.endswith("…")
    assert len(conv.title) <= 61  # ≤60 chars (rstrip may shorten) + the ellipsis
    assert len(conv.title) < len(long_text)


def test_create_collapses_whitespace_in_title(db) -> None:
    conv = conversations.create_conversation(
        db, messages=_messages("  what   is\nmy balance?  ")
    )
    assert conv.title == "what is my balance?"


def test_create_with_explicit_title(db) -> None:
    conv = conversations.create_conversation(
        db, messages=_messages("hello"), title="My chat"
    )
    assert conv.title == "My chat"


def test_list_orders_by_updated_at_desc(db) -> None:
    first = conversations.create_conversation(db, messages=_messages("first"))
    second = conversations.create_conversation(db, messages=_messages("second"))
    # Set distinct updated_at values: CURRENT_TIMESTAMP has second precision,
    # so real time can't order rows created within the same test run.
    first.updated_at = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    second.updated_at = datetime.datetime(2026, 2, 1, tzinfo=datetime.timezone.utc)
    db.commit()
    rows = conversations.list_conversations(db)
    assert [row.id for row in rows] == [second.id, first.id]


def test_get_not_found_raises(db) -> None:
    with pytest.raises(NotFoundError):
        conversations.get_conversation(db, 9999)


def test_save_updates_messages_and_last_done(db) -> None:
    conv = conversations.create_conversation(db, messages=_messages("hi"))
    done = {"answer": "42", "trail": [], "proposals": []}
    saved = conversations.save_conversation(
        db, conv.id, messages=_messages("hi"), last_done=done
    )
    assert json.loads(saved.messages_json) == _messages("hi")
    assert json.loads(saved.last_done_json) == done


def test_save_clears_last_done(db) -> None:
    conv = conversations.create_conversation(db, messages=_messages("hi"))
    conversations.save_conversation(
        db,
        conv.id,
        messages=_messages("hi"),
        last_done={"answer": "x", "trail": [], "proposals": []},
    )
    saved = conversations.save_conversation(
        db, conv.id, messages=_messages("hi"), last_done=None
    )
    assert saved.last_done_json is None


def test_delete_removes(db) -> None:
    conv = conversations.create_conversation(db, messages=_messages("hi"))
    conversations.delete_conversation(db, conv.id)
    with pytest.raises(NotFoundError):
        conversations.get_conversation(db, conv.id)


def test_no_audit_rows_for_conversations(db) -> None:
    """ChatConversation CRUD must not produce any AuditLog rows."""
    conv = conversations.create_conversation(db, messages=_messages("hi"))
    conversations.save_conversation(
        db,
        conv.id,
        messages=_messages("hi"),
        last_done={"answer": "x", "trail": [], "proposals": []},
    )
    conversations.delete_conversation(db, conv.id)
    rows = db.scalars(
        select(AuditLog).where(AuditLog.model == "ChatConversation")
    ).all()
    assert rows == []
