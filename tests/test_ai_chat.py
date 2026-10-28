"""Tests for the AI command center agent loop and REST endpoints.

The LLM is a scripted fake: ``llm.stream_chat`` is monkeypatched with a
per-round chunk generator (the last scripted round repeats, so a fake
that always asks for a tool call can exercise the iteration cap), and
``llm.list_models`` is stubbed so the router's reachability probe never
touches the network.
"""

import datetime
import json
from typing import Any

import pytest

from app.database import SessionLocal
from app.models.audit import AuditLog
from app.services import ai_chat, audit as audit_service, llm
from app.services.errors import LLMError


# --- scripted fake LLM ------------------------------------------------------


def _content(text: str) -> dict[str, Any]:
    return {"choices": [{"delta": {"content": text}, "finish_reason": None}]}


def _tool_call(call_id: str, name: str, arguments: str) -> dict[str, Any]:
    return {
        "choices": [
            {
                "delta": {
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": call_id,
                            "function": {"name": name, "arguments": arguments},
                        }
                    ]
                },
                "finish_reason": None,
            }
        ]
    }


def _finish(reason: str) -> dict[str, Any]:
    return {"choices": [{"delta": {}, "finish_reason": reason}]}


def _script(monkeypatch: pytest.MonkeyPatch, rounds: list[list[dict[str, Any]]]):
    """Point ``llm.stream_chat`` at scripted chunks; stub ``list_models``.

    Returns a list capturing the message array of every model call.
    """
    state = {"call": 0}
    captured: list[list[dict[str, Any]]] = []

    def fake_stream_chat(messages: list[dict[str, Any]], tools: Any = None):
        captured.append(list(messages))
        yield from rounds[min(state["call"], len(rounds) - 1)]
        state["call"] += 1

    monkeypatch.setattr(llm, "stream_chat", fake_stream_chat)
    monkeypatch.setattr(llm, "list_models", lambda: ["fake-model"])
    return captured


def _events(response) -> list[dict[str, Any]]:
    """Parse the SSE stream of a TestClient streaming response."""
    events = []
    for line in response.iter_lines():
        line = line.strip()
        if line.startswith("data: "):
            events.append(json.loads(line[len("data: ") :]))
    return events


def _chat(client, message: str):
    return client.stream(
        "POST", "/api/ai/chat", json={"messages": [{"role": "user", "content": message}]}
    )


# --- chat: agent loop --------------------------------------------------------


def test_chat_read_qa_streams_tool_then_answer(client, monkeypatch):
    _script(
        monkeypatch,
        [
            [_tool_call("call_1", "list_accounts", "{}"), _finish("tool_calls")],
            [_content("You have accounts."), _finish("stop")],
        ],
    )
    with _chat(client, "List my accounts") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        events = _events(response)

    assert [event["type"] for event in events] == ["tool", "delta", "done"]
    tool = events[0]
    assert tool["tool"] == "list_accounts"
    assert tool["args"] == {}
    assert tool["ok"] is True
    assert tool["summary"].endswith("items")
    done = events[-1]
    assert done["answer"] == "You have accounts."
    assert done["trail"] == [tool]
    assert done["proposals"] == []
    # The done event carries the full conversation for the next turn.
    assert [m["role"] for m in done["messages"]] == [
        "system",
        "user",
        "assistant",
        "tool",
    ]


def test_chat_write_becomes_proposal_not_executed(client, monkeypatch):
    _script(
        monkeypatch,
        [
            [
                _tool_call("call_1", "create_customer", '{"name": "Proposed Co"}'),
                _finish("tool_calls"),
            ]
        ],
    )
    with _chat(client, "Add Proposed Co as a customer") as response:
        events = _events(response)

    assert [event["type"] for event in events] == ["proposal", "done"]
    proposal = events[0]
    assert proposal == {
        "type": "proposal",
        "id": "p1",
        "tool": "create_customer",
        "args": {"name": "Proposed Co"},
    }
    done = events[1]
    assert done["proposals"] == [
        {"id": "p1", "tool": "create_customer", "args": {"name": "Proposed Co"}}
    ]
    # The write must not have run: no customer, no audit row for it.
    ok, result = ai_chat.execute_tool("list_customers", {}, "test")
    assert ok and "Proposed Co" not in result
    db = SessionLocal()
    rows = db.query(AuditLog).filter_by(model="Customer").all()
    db.close()
    assert rows == []


def test_chat_tool_error_in_trail_is_not_fatal(client, monkeypatch):
    _script(
        monkeypatch,
        [
            [
                _tool_call("call_1", "get_invoice", '{"invoice_id": 9999}'),
                _finish("tool_calls"),
            ],
            [_content("No such invoice."), _finish("stop")],
        ],
    )
    with _chat(client, "Show me invoice 9999") as response:
        events = _events(response)

    tool = events[0]
    assert tool["ok"] is False
    assert "9999" in tool["summary"]
    assert [event["type"] for event in events] == ["tool", "delta", "done"]


def test_chat_iteration_cap_ends_with_error(client, monkeypatch):
    # The single scripted round repeats: the model never stops calling.
    _script(
        monkeypatch,
        [[_tool_call("call_1", "list_accounts", "{}"), _finish("tool_calls")]],
    )
    with _chat(client, "Loop forever") as response:
        events = _events(response)

    assert events[-1]["type"] == "error"
    assert "limit" in events[-1]["detail"]
    assert sum(1 for e in events if e["type"] == "tool") == ai_chat.MAX_ROUNDS


def test_chat_system_prompt_prepended_when_missing(client, monkeypatch):
    captured = _script(monkeypatch, [[_content("ok"), _finish("stop")]])
    with _chat(client, "hi") as response:
        list(response.iter_lines())
    first_call = captured[0]
    assert first_call[0]["role"] == "system"
    assert first_call[0]["content"] == ai_chat.SYSTEM_PROMPT


def test_chat_system_prompt_not_duplicated_when_present(client, monkeypatch):
    captured = _script(monkeypatch, [[_content("ok"), _finish("stop")]])
    messages = [
        {"role": "system", "content": "custom system prompt"},
        {"role": "user", "content": "hi"},
    ]
    with client.stream("POST", "/api/ai/chat", json={"messages": messages}) as response:
        list(response.iter_lines())
    first_call = captured[0]
    assert first_call[0] == {"role": "system", "content": "custom system prompt"}
    assert sum(1 for m in first_call if m["role"] == "system") == 1


# --- chat: LLM failures ------------------------------------------------------


def test_chat_llm_down_fails_fast_with_503(client, monkeypatch):
    def broken_models():
        raise LLMError("LLM unreachable: connection refused")

    monkeypatch.setattr(llm, "list_models", broken_models)
    response = client.post(
        "/api/ai/chat", json={"messages": [{"role": "user", "content": "hi"}]}
    )
    assert response.status_code == 503
    assert "LLM unreachable" in response.json()["detail"]


def test_chat_mid_stream_llm_error_emits_error_event(client, monkeypatch):
    def broken_stream(messages, tools=None):
        yield _content("partial")
        raise LLMError("LLM unreachable: connection reset mid-stream")

    monkeypatch.setattr(llm, "stream_chat", broken_stream)
    monkeypatch.setattr(llm, "list_models", lambda: ["fake-model"])
    with _chat(client, "hi") as response:
        assert response.status_code == 200  # streaming had started
        events = _events(response)
    assert events == [
        {"type": "delta", "text": "partial"},
        {"type": "error", "detail": "LLM unreachable: connection reset mid-stream"},
    ]


# --- chat: protocol ----------------------------------------------------------


def test_chat_sse_framing(client, monkeypatch):
    _script(monkeypatch, [[_content("hi"), _finish("stop")]])
    with _chat(client, "hi") as response:
        lines = [line for line in response.iter_lines() if line.strip()]
    assert lines
    for line in lines:
        assert line.startswith("data: ")
        json.loads(line[len("data: ") :])  # every data line is valid JSON


def test_chat_rejects_messages_without_roles(client):
    response = client.post(
        "/api/ai/chat", json={"messages": [{"content": "no role"}]}
    )
    assert response.status_code == 422


# --- approve -----------------------------------------------------------------


def test_approve_posts_write_audited_as_command_center(client):
    response = client.post(
        "/api/ai/approve", json={"tool": "create_customer", "args": {"name": "Approved Co"}}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert "Approved Co" in body["result"]
    db = SessionLocal()
    rows = (
        db.query(AuditLog)
        .filter_by(actor=audit_service.AI_COMMAND_CENTER_ACTOR, model="Customer")
        .all()
    )
    db.close()
    assert len(rows) == 1


def test_approve_locked_month_returns_409(client):
    today = datetime.date.today()
    month = today.strftime("%Y-%m")
    lock = client.post(
        "/api/ai/approve", json={"tool": "lock_period", "args": {"month": month}}
    )
    assert lock.status_code == 200
    entry = client.post(
        "/api/ai/approve",
        json={
            "tool": "create_journal_entry",
            "args": {
                "date": today.isoformat(),
                "description": "AI entry",
                "lines": [
                    {"account": "1000", "debit_cents": 100},
                    {"account": "4000", "credit_cents": 100},
                ],
            },
        },
    )
    assert entry.status_code == 409
    assert "locked" in entry.json()["detail"]


def test_approve_unknown_tool_returns_404(client):
    response = client.post(
        "/api/ai/approve", json={"tool": "no_such_tool", "args": {}}
    )
    assert response.status_code == 404
    assert "no_such_tool" in response.json()["detail"]


def test_approve_bad_args_returns_422(client):
    response = client.post(
        "/api/ai/approve", json={"tool": "create_customer", "args": {}}
    )
    assert response.status_code == 422


# --- status ------------------------------------------------------------------


def test_status_reachable(client, monkeypatch):
    monkeypatch.setattr(llm, "list_models", lambda: ["fake-model"])
    response = client.get("/api/ai/status")
    assert response.status_code == 200
    body = response.json()
    assert body["reachable"] is True
    assert body["model"] == "fake-model"
    assert body["base"] == llm.api_base()


def test_status_unreachable(client, monkeypatch):
    def broken_models():
        raise LLMError("LLM unreachable: connection refused")

    monkeypatch.setattr(llm, "list_models", broken_models)
    body = client.get("/api/ai/status").json()
    assert body["reachable"] is False
    assert body["model"] is None
    assert "LLM unreachable" in body["error"]


# --- auth --------------------------------------------------------------------


def test_unauthenticated_endpoints_return_401(app_client):
    chat = app_client.post(
        "/api/ai/chat", json={"messages": [{"role": "user", "content": "hi"}]}
    )
    approve = app_client.post(
        "/api/ai/approve", json={"tool": "create_customer", "args": {}}
    )
    status = app_client.get("/api/ai/status")
    assert chat.status_code == 401
    assert approve.status_code == 401
    assert status.status_code == 401
