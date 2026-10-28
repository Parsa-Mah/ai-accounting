"""Pydantic schemas for the AI command center endpoints."""

from typing import Any

from pydantic import BaseModel, Field, field_validator


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
