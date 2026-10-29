"""AI chat conversation model.

A :class:`ChatConversation` is one AI command-center thread. It stores the
full OpenAI ``messages`` array (the exact state to replay the conversation)
plus the most recent ``done`` event's ``{answer, trail, proposals}`` so a
reloaded page can re-render the last answer, its tool trail, and any
pending proposals without re-running the model.

Conversations are deliberately kept out of the audit trail (see
``_SKIP`` in ``app/services/audit.py``): they are UI state, not writes to
the books, and every real write they trigger is already audited through the
tool bridge.
"""

import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ChatConversation(Base):
    __tablename__ = "chat_conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    # The full OpenAI message array, as a JSON string.
    messages_json: Mapped[str] = mapped_column(Text, default="[]")
    # The last ``done`` event's {answer, trail, proposals}, as a JSON string.
    # Nullable: a conversation with no completed turn has none yet.
    last_done_json: Mapped[str | None] = mapped_column(Text, nullable=True)
