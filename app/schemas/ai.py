"""Pydantic schemas for the AI command center endpoints."""

import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatIn(BaseModel):
    """Chat request: the raw OpenAI message array for the conversation.

    Validated loosely — messages are passed through to the LLM as-is
    (every message just needs a string ``role``).
    """

    messages: list[dict[str, Any]] = Field(min_length=1)

    @field_validator("messages")
    @classmethod
    def _check_roles(cls, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for message in messages:
            if not isinstance(message.get("role"), str):
                raise ValueError("every message needs a string 'role'")
        return messages


class ApproveIn(BaseModel):
    """An approved proposal: the write tool to execute with its arguments."""

    tool: str
    args: dict[str, Any] = Field(default_factory=dict)


class ConversationCreate(BaseModel):
    """Create a conversation from its initial message array.

    ``title`` is optional; when omitted the server derives it from the first
    user message.
    """

    messages: list[dict[str, Any]] = Field(min_length=1)
    title: str | None = None


class ConversationSave(BaseModel):
    """Persist a completed turn: the new message array + last ``done`` state.

    ``last_done`` is the ``{answer, trail, proposals}`` dict from the most
    recent ``done`` event, or ``None`` to clear it.
    """

    messages: list[dict[str, Any]]
    last_done: dict[str, Any] | None = None


class ConversationRead(BaseModel):
    """A conversation summary for the picker list (no message payload)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


class ConversationDetail(BaseModel):
    """A full conversation: the message array + last completed turn."""

    id: int
    title: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    messages: list[dict[str, Any]]
    last_done: dict[str, Any] | None
