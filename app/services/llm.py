"""Local LLM client for the AI command center (OpenAI-compatible API).

Streams chat completions from a local OpenAI-compatible endpoint (LM
Studio by default). All configuration comes from the environment, read
at call time so tests can monkeypatch:

- ``LLM_API_BASE`` — base URL (default ``http://127.0.0.1:1234/v1``)
- ``LLM_MODEL`` — model id; when unset, the first model reported by
  ``GET {base}/models`` is used and cached
- ``LLM_API_KEY`` — bearer key (default empty; LM Studio needs none)
- ``LLM_EXTRA`` — optional JSON object merged into the chat request body
  (escape hatch for provider-specific options, e.g. thinking toggles)

Every failure raises :class:`~app.services.errors.LLMError` (mapped to
HTTP 503 by ``create_app``). ``_client()`` is the test seam: tests swap
it for a factory backed by ``httpx.MockTransport``.
"""

import json
import os
from collections.abc import Iterator
from typing import Any

import httpx

from app.services.errors import LLMError

__all__ = ["api_base", "list_models", "resolve_model", "stream_chat"]

DEFAULT_BASE = "http://127.0.0.1:1234/v1"

# Local models are slow between chunks: generous read timeout, short
# connect timeout so a stopped server fails fast.
_CHAT_TIMEOUT = httpx.Timeout(300.0, connect=5.0)
_MODELS_TIMEOUT = 3.0

# Cache of the auto-detected model id (only used while LLM_MODEL is unset).
_cached_model: str | None = None


def api_base() -> str:
    """The configured base URL (no trailing slash)."""
    return os.environ.get("LLM_API_BASE", DEFAULT_BASE).rstrip("/")


def _headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    key = os.environ.get("LLM_API_KEY", "")
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return headers


def _extra_body() -> dict[str, Any]:
    """Parse ``LLM_EXTRA`` (JSON object) for merging into the request body."""
    raw = os.environ.get("LLM_EXTRA", "").strip()
    if not raw:
        return {}
    try:
        extra = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMError(f"LLM_EXTRA is not valid JSON: {exc}") from exc
    if not isinstance(extra, dict):
        raise LLMError("LLM_EXTRA must be a JSON object")
    return extra


def _client() -> httpx.Client:
    """Client factory — the test seam (tests back it with MockTransport)."""
    return httpx.Client(timeout=_CHAT_TIMEOUT)


def list_models() -> list[str]:
    """Model ids served by the endpoint (``GET {base}/models``)."""
    try:
        with _client() as client:
            response = client.get(
                f"{api_base()}/models", headers=_headers(), timeout=_MODELS_TIMEOUT
            )
    except httpx.HTTPError as exc:
        raise LLMError(f"LLM unreachable: {exc}") from exc
    if response.status_code != 200:
        raise LLMError(f"LLM models request failed: HTTP {response.status_code}")
    try:
        data = response.json().get("data", [])
    except ValueError as exc:
        raise LLMError("LLM models response is not valid JSON") from exc
    return [
        item["id"] for item in data if isinstance(item, dict) and "id" in item
    ]


def resolve_model() -> str:
    """The model id to use: ``LLM_MODEL`` or the first auto-detected one.

    Auto-detection hits ``GET {base}/models`` once and caches the result
    for the process lifetime; setting ``LLM_MODEL`` always wins.
    """
    global _cached_model
    explicit = os.environ.get("LLM_MODEL", "").strip()
    if explicit:
        return explicit
    if _cached_model is None:
        models = list_models()
        if not models:
            raise LLMError(f"No models available at {api_base()}")
        _cached_model = models[0]
    return _cached_model


def stream_chat(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
) -> Iterator[dict[str, Any]]:
    """Stream chat completions, yielding one raw chunk dict per SSE event.

    Posts ``{base}/chat/completions`` with ``stream: true`` and yields the
    parsed JSON of every ``data:`` line until ``data: [DONE]``. Comment
    lines (``: …``), blank separators, and non-``data`` event fields are
    ignored. Any failure raises :class:`LLMError`.
    """
    body: dict[str, Any] = {
        "model": resolve_model(),
        "messages": messages,
        "stream": True,
        "temperature": 0.2,
        "max_tokens": 4096,
    }
    if tools:
        body["tools"] = tools
    body.update(_extra_body())
    try:
        with _client() as client:
            with client.stream(
                "POST",
                f"{api_base()}/chat/completions",
                json=body,
                headers=_headers(),
            ) as response:
                if response.status_code != 200:
                    response.read()
                    raise LLMError(
                        f"LLM chat request failed: HTTP {response.status_code} "
                        f"({response.text[:200]})"
                    )
                for line in response.iter_lines():
                    line = line.strip()
                    if not line or line.startswith(":"):
                        continue
                    if not line.startswith("data:"):
                        continue
                    payload = line[len("data:") :].strip()
                    if payload == "[DONE]":
                        return
                    try:
                        yield json.loads(payload)
                    except json.JSONDecodeError as exc:
                        raise LLMError(
                            f"Malformed SSE chunk from LLM: {payload!r}"
                        ) from exc
    except httpx.HTTPError as exc:
        raise LLMError(f"LLM unreachable: {exc}") from exc
