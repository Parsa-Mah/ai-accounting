"""AI chat conversation service.

CRUD for :class:`~app.models.chat.ChatConversation` rows. Conversations are
UI state for the AI command center: they hold the full OpenAI message array
and the last completed turn so a reloaded page can re-render without
re-running the model. They are kept out of the audit trail (see ``_SKIP`` in
``app/services/audit.py``) — every real write a conversation triggers is
audited through the tool bridge instead.

The title is derived server-side from the first user message when the
caller does not supply one, keeping the client dumb and the list readable.
"""

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chat import ChatConversation
from app.services.errors import NotFoundError

# How long a derived title may be before it is truncated (with an ellipsis).
_TITLE_MAX = 60


def _derive_title(messages: list[dict]) -> str:
    """Derive a short display title from the first user message.

    Whitespace is collapsed and the text truncated to ``_TITLE_MAX`` chars.
    Falls back to an empty string when there is no user message (the model
    default then applies).
    """
    for message in messages:
        if message.get("role") == "user":
            text = " ".join(str(message.get("content", "")).split())
            if len(text) > _TITLE_MAX:
                return text[:_TITLE_MAX].rstrip() + "…"
            return text
    return ""


def create_conversation(
    db: Session, *, messages: list[dict], title: str | None = None
) -> ChatConversation:
    """Create a conversation from its initial message array.

    ``title`` is optional; when omitted it is derived from the first user
    message. ``last_done`` is unset — no turn has completed yet.
    """
    conv = ChatConversation(
        title=title if title is not None else _derive_title(messages),
        messages_json=json.dumps(messages, ensure_ascii=False),
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def list_conversations(db: Session) -> list[ChatConversation]:
    """All conversations, most recently updated first."""
    return list(
        db.scalars(
            select(ChatConversation).order_by(
                ChatConversation.updated_at.desc(), ChatConversation.id.desc()
            )
        )
    )


def get_conversation(db: Session, conversation_id: int) -> ChatConversation:
    conv = db.get(ChatConversation, conversation_id)
    if conv is None:
        raise NotFoundError(f"conversation {conversation_id} not found")
    return conv


def save_conversation(
    db: Session,
    conversation_id: int,
    *,
    messages: list[dict],
    last_done: dict | None,
) -> ChatConversation:
    """Persist a completed turn: the new message array + last ``done`` state.

    ``last_done`` is the ``{answer, trail, proposals}`` dict from the most
    recent ``done`` event, or ``None`` to clear it. Bumping ``updated_at``
    is handled by the model's ``onupdate``.
    """
    conv = get_conversation(db, conversation_id)
    conv.messages_json = json.dumps(messages, ensure_ascii=False)
    conv.last_done_json = (
        json.dumps(last_done, ensure_ascii=False) if last_done is not None else None
    )
    db.commit()
    db.refresh(conv)
    return conv


def delete_conversation(db: Session, conversation_id: int) -> None:
    conv = get_conversation(db, conversation_id)
    db.delete(conv)
    db.commit()
