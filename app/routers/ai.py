"""AI command center endpoints: streaming chat, approval, status.

Chat streams Server-Sent Events (one JSON object per ``data:`` line) —
the agent loop acts through the typed MCP tools, reads execute
immediately, writes come back as proposals. Approval executes a
human-approved write through the same bridge (audited as
``ai:command-center``). If the LLM backend is down at request time the
chat request fails fast with 503 (``LLMError`` handler); a failure
mid-stream surfaces as an SSE ``error`` event instead.
"""

import json
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.chat import ChatConversation
from app.schemas.ai import (
    ApproveIn,
    ChatIn,
    ConversationCreate,
    ConversationDetail,
    ConversationRead,
    ConversationSave,
)
from app.services import ai_chat, conversations, llm
from app.services import audit as audit_service

router = APIRouter(
    prefix="/api/ai", tags=["ai"], dependencies=[Depends(get_current_user)]
)


def _sse(events: Iterator[dict[str, Any]]) -> Iterator[str]:
    """Frame event dicts as Server-Sent Events (one ``data:`` line each)."""
    for event in events:
        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@router.post("/chat")
def chat(body: ChatIn) -> StreamingResponse:
    # Probe first: backend down -> LLMError -> 503 before streaming
    # starts. (A failure mid-stream becomes an SSE ``error`` event.)
    llm.list_models()
    events = ai_chat.run_chat_stream(
        body.messages, audit_service.AI_COMMAND_CENTER_ACTOR
    )
    return StreamingResponse(_sse(events), media_type="text/event-stream")


@router.post("/approve")
def approve(body: ApproveIn) -> dict[str, Any]:
    # Domain errors re-raise as NotFoundError/ConflictError/ValidationError
    # -> the standard 404/409/422 handlers (e.g. locked month -> 409).
    return ai_chat.approve(
        body.tool, body.args, audit_service.AI_COMMAND_CENTER_ACTOR
    )


@router.get("/status")
def status() -> dict[str, Any]:
    return ai_chat.status()


def _to_detail(conv: ChatConversation) -> ConversationDetail:
    """Render a conversation ORM row as the detail schema (JSON parsed)."""
    return ConversationDetail(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=json.loads(conv.messages_json) if conv.messages_json else [],
        last_done=json.loads(conv.last_done_json) if conv.last_done_json else None,
    )


@router.get("/conversations", response_model=list[ConversationRead])
def list_conversations(db: Session = Depends(get_db)) -> list[ChatConversation]:
    return conversations.list_conversations(db)


@router.post(
    "/conversations", response_model=ConversationRead, status_code=201
)
def create_conversation(
    body: ConversationCreate, db: Session = Depends(get_db)
) -> ChatConversation:
    return conversations.create_conversation(
        db, messages=body.messages, title=body.title
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: int, db: Session = Depends(get_db)
) -> ConversationDetail:
    return _to_detail(conversations.get_conversation(db, conversation_id))


@router.put("/conversations/{conversation_id}", response_model=ConversationDetail)
def save_conversation(
    conversation_id: int,
    body: ConversationSave,
    db: Session = Depends(get_db),
) -> ConversationDetail:
    return _to_detail(
        conversations.save_conversation(
            db, conversation_id, messages=body.messages, last_done=body.last_done
        )
    )


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: int, db: Session = Depends(get_db)) -> None:
    conversations.delete_conversation(db, conversation_id)
    return None
