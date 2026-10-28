"""Tests for the local LLM client (app/services/llm.py).

All HTTP goes through ``httpx.MockTransport`` via the module's client
factory seam (``llm._client``), so no network is touched.
"""

import json

import httpx
import pytest

from app.services import llm
from app.services.errors import LLMError

MESSAGES = [{"role": "user", "content": "What's my cash balance?"}]
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_cash_balance",
            "description": "Current cash balance",
            "parameters": {"type": "object", "properties": {}},
        },
    }
]


def _sse_response(*chunks: bytes) -> httpx.Response:
    """A streaming SSE response assembled from raw byte chunks."""
    return httpx.Response(
        200,
        headers={"content-type": "text/event-stream"},
        content=iter(chunks),
    )


def _install(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    """Point the client factory at a MockTransport with the given handler."""

    def factory() -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(llm, "_client", factory)


def test_stream_chat_parses_sse_chunks(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "test-model")

    def handler(request: httpx.Request) -> httpx.Response:
        return _sse_response(
            b": OPENAI keepalive comment\n\n",
            b'data: {"choices": [{"delta": {"content": "Hel"}}]}\n',
            b"\n",
            b"event: x\n",  # non-data event field: ignored
            b'data: {"choices": [{"delta": {"content": "lo"}}]}\n\n',
            b"data: [DONE]\n\n",
            b'data: {"choices": [{"delta": {"content": "late"}}]}\n\n',
        )

    _install(monkeypatch, handler)
    chunks = list(llm.stream_chat(MESSAGES))
    assert [c["choices"][0]["delta"]["content"] for c in chunks] == ["Hel", "lo"]


def test_stream_chat_request_body(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "test-model")
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        captured["headers"] = dict(request.headers)
        return _sse_response(b"data: [DONE]\n")

    _install(monkeypatch, handler)
    list(llm.stream_chat(MESSAGES, tools=TOOLS))

    body = captured["body"]
    assert body["model"] == "test-model"
    assert body["messages"] == MESSAGES
    assert body["stream"] is True
    assert body["temperature"] == 0.2
    assert body["max_tokens"] == 4096
    assert body["tools"] == TOOLS
    assert "authorization" not in captured["headers"]  # LLM_API_KEY unset


def test_stream_chat_without_tools_omits_key(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "test-model")
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return _sse_response(b"data: [DONE]\n")

    _install(monkeypatch, handler)
    list(llm.stream_chat(MESSAGES))
    assert "tools" not in captured["body"]


def test_model_auto_detect_and_cache(monkeypatch):
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.setattr(llm, "_cached_model", None)
    calls = {"models": 0}
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            calls["models"] += 1
            return httpx.Response(
                200, json={"data": [{"id": "qwen3-8b"}, {"id": "other"}]}
            )
        captured["body"] = json.loads(request.content)
        return _sse_response(b"data: [DONE]\n")

    _install(monkeypatch, handler)
    list(llm.stream_chat(MESSAGES))
    list(llm.stream_chat(MESSAGES))
    assert calls["models"] == 1  # detected once, cached for the second call
    assert captured["body"]["model"] == "qwen3-8b"


def test_explicit_model_env_wins(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "explicit-model")
    calls = {"models": 0}
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            calls["models"] += 1
            return httpx.Response(200, json={"data": [{"id": "detected"}]})
        captured["body"] = json.loads(request.content)
        return _sse_response(b"data: [DONE]\n")

    _install(monkeypatch, handler)
    list(llm.stream_chat(MESSAGES))
    assert calls["models"] == 0
    assert captured["body"]["model"] == "explicit-model"


def test_resolve_model_no_models_available(monkeypatch):
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.setattr(llm, "_cached_model", None)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": []})

    _install(monkeypatch, handler)
    with pytest.raises(LLMError, match="No models available"):
        llm.resolve_model()


def test_api_key_header(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("LLM_API_KEY", "secret-key")
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        return _sse_response(b"data: [DONE]\n")

    _install(monkeypatch, handler)
    list(llm.stream_chat(MESSAGES))
    assert captured["headers"]["authorization"] == "Bearer secret-key"


def test_llm_extra_merged_into_body(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("LLM_EXTRA", '{"enable_thinking": false, "top_p": 0.9}')
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return _sse_response(b"data: [DONE]\n")

    _install(monkeypatch, handler)
    list(llm.stream_chat(MESSAGES))
    assert captured["body"]["enable_thinking"] is False
    assert captured["body"]["top_p"] == 0.9


def test_llm_extra_invalid_json_raises(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("LLM_EXTRA", "not-json")
    _install(monkeypatch, lambda request: _sse_response(b"data: [DONE]\n"))
    with pytest.raises(LLMError, match="LLM_EXTRA is not valid JSON"):
        list(llm.stream_chat(MESSAGES))


def test_connect_failure_raises_llm_error(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "test-model")

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    _install(monkeypatch, handler)
    with pytest.raises(LLMError, match="LLM unreachable"):
        list(llm.stream_chat(MESSAGES))


def test_http_error_status_raises_llm_error(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "test-model")
    _install(
        monkeypatch, lambda request: httpx.Response(500, text="internal error")
    )
    with pytest.raises(LLMError, match="HTTP 500"):
        list(llm.stream_chat(MESSAGES))


def test_malformed_sse_chunk_raises(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "test-model")
    _install(monkeypatch, lambda request: _sse_response(b"data: {not json}\n"))
    with pytest.raises(LLMError, match="Malformed SSE chunk"):
        list(llm.stream_chat(MESSAGES))


def test_list_models(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/models")
        return httpx.Response(200, json={"data": [{"id": "a"}, {"id": "b"}]})

    _install(monkeypatch, handler)
    assert llm.list_models() == ["a", "b"]


def test_list_models_unreachable(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    _install(monkeypatch, handler)
    with pytest.raises(LLMError, match="LLM unreachable"):
        llm.list_models()
