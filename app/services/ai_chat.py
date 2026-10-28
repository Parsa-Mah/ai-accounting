"""AI command center: the local LLM acting through the typed MCP tools.

The command center reuses the MCP tool surface as the LLM's action
vocabulary: every tool is already a thin, typed wrapper over the domain
services (single posting path), so the web AI and the MCP server can
never disagree. This module is the bridge between the two worlds:

- :func:`tool_schemas` — the 50 tools as OpenAI function-calling schemas
- :func:`execute_tool` — run one tool by name, errors as strings (never
  raised) so the LLM can read them and recover
- actor override — every execution audits as ``ai:command-center``
  (see ``audit.set_actor_override``)

The agent loop (``run_chat_stream``) streams one event dict per SSE
event; ``approve`` executes a human-approved write; ``status`` reports
backend reachability for the chat page.
"""

import json
import os
from collections.abc import Callable, Iterator
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError

from app.mcp import tools
from app.mcp.server import build_server
from app.services import audit as audit_service
from app.services import llm
from app.services.errors import (
    ConflictError,
    LLMError,
    NotFoundError,
    ValidationError,
)

__all__ = [
    "SYSTEM_PROMPT",
    "WRITE_TOOL_NAMES",
    "approve",
    "execute_tool",
    "run_chat_stream",
    "status",
    "tool_schemas",
]

SYSTEM_PROMPT = (
    "You are the assistant for this business's books. Every fact you "
    "state must come from a tool result — never invent balances, "
    "amounts, dates, or record ids.\n\n"
    "Money: tool results carry integer cents plus formatted *_usd "
    "strings; quote the *_usd values directly.\n\n"
    "Read tools (list_*, get_*, search_*, statements, ledgers, exports): "
    "call them freely, as many as you need.\n\n"
    "Write tools (create_*, pay_*, void_*, lock_*, unlock_*, delete_*): "
    "calling one only PROPOSES the action. The system shows the proposal "
    "to the user and asks for approval before executing it. You will not "
    "see the result this turn, so say what you proposed and why — never "
    "that it was done.\n\n"
    "Cite record ids in your answers (e.g. \"Invoice #7\") so the user "
    "can open them. Answer in the language the user writes in. Be "
    "concise."
)

# Hard cap on model rounds per turn: a misbehaving model that keeps
# calling tools must not loop forever.
MAX_ROUNDS = 8

# Write tools are proposals in the command center: they are never
# executed by the agent loop, only after explicit human approval.
WRITE_TOOL_NAMES: frozenset[str] = frozenset(
    fn.__name__ for fn in tools.write_tools()
)

# Dispatch map: tool name -> wrapped function (functools.wraps keeps
# the original __name__ through @context.safe_tool).
_TOOL_MAP: dict[str, Callable[..., Any]] = {
    fn.__name__: fn for fn in [*tools.read_tools(), *tools.write_tools()]
}

# Tool results are JSON-serialized for the LLM; very large results are
# truncated so one tool cannot blow the context window.
_MAX_RESULT_CHARS = 4000

_schemas: list[dict[str, Any]] | None = None


def _openai_params(parameters: dict[str, Any]) -> dict[str, Any]:
    """The SDK JSON schema minus the cosmetic top-level ``title``."""
    return {key: value for key, value in parameters.items() if key != "title"}


def tool_schemas() -> list[dict[str, Any]]:
    """OpenAI function-calling schemas for the full 50-tool surface.

    Built once (cached) from ``build_server(allow_write=True)`` so the
    command center always sees reads and writes, regardless of
    ``MCP_ALLOW_WRITE``.
    """
    global _schemas
    if _schemas is None:
        server = build_server(allow_write=True)
        _schemas = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": _openai_params(tool.parameters),
                },
            }
            for tool in server._tool_manager.list_tools()
        ]
    return _schemas


def _serialize(result: Any) -> str:
    """JSON-serialize a tool result, truncating oversized payloads."""
    text = json.dumps(result, default=str)
    if len(text) > _MAX_RESULT_CHARS:
        text = text[:_MAX_RESULT_CHARS] + "… (truncated)"
    return text


def execute_tool(
    name: str, args: dict[str, Any], actor: str
) -> tuple[bool, str]:
    """Run one MCP tool by name with the given audit actor.

    The actor is set as an override for the execution (reads included,
    for uniformity), so every write lands in the audit trail attributed
    to the command center. Returns ``(ok, result_or_error)``: tool
    errors and bad arguments come back as error strings, never
    exceptions — the LLM reads them and recovers.
    """
    fn = _TOOL_MAP.get(name)
    if fn is None:
        return False, f"Unknown tool '{name}'"
    override_token = audit_service.set_actor_override(actor)
    try:
        result = fn(**args)
    except (ToolError, TypeError) as exc:
        return False, str(exc) or f"Tool '{name}' failed"
    except Exception as exc:
        # A tool must never crash the agent loop; the LLM needs a
        # readable error to recover from.
        return False, f"Tool '{name}' failed: {exc}"
    finally:
        audit_service.reset_actor_override(override_token)
    return True, _serialize(result)


def approve(tool: str, args: dict[str, Any], actor: str) -> dict[str, Any]:
    """Execute a human-approved write tool.

    Unlike :func:`execute_tool` (errors come back as strings the LLM
    reads), domain errors re-raise here so the standard handlers map
    them to HTTP statuses — 404 unknown tool, 409 locked period, 422
    bad arguments. The write still runs under the actor override, so it
    lands in the audit trail as the command center.
    """
    fn = _TOOL_MAP.get(tool)
    if fn is None:
        raise NotFoundError(f"Unknown tool '{tool}'")
    override_token = audit_service.set_actor_override(actor)
    try:
        result = fn(**args)
    except ToolError as exc:
        cause = exc.__cause__
        if isinstance(cause, (NotFoundError, ConflictError, ValidationError)):
            raise cause from exc
        raise ValidationError(str(exc)) from exc
    except TypeError as exc:
        raise ValidationError(str(exc)) from exc
    finally:
        audit_service.reset_actor_override(override_token)
    return {"ok": True, "result": _serialize(result)}


def _parse_args(raw: str) -> dict[str, Any] | None:
    """Parse a tool call's JSON arguments (None if malformed)."""
    if not raw.strip():
        return {}
    try:
        args = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return args if isinstance(args, dict) else None


def _summarize(ok: bool, result: str) -> str:
    """Short trail-chip summary: 'N items' for lists, error text on failure."""
    if not ok:
        return result[:200]
    try:
        parsed = json.loads(result)
    except json.JSONDecodeError:
        return "ok"
    if isinstance(parsed, list):
        return f"{len(parsed)} items"
    return "ok"


def run_chat_stream(
    messages: list[dict[str, Any]],
    actor: str,
) -> Iterator[dict[str, Any]]:
    """The agent loop as a stream of event dicts (one per SSE event).

    Events: ``delta`` (streamed answer text), ``tool`` (a read tool ran),
    ``proposal`` (a write tool awaits human approval), ``error`` (LLM
    failure — terminal), ``done`` (turn complete — terminal; carries the
    full message array for the next turn).

    Writes are never executed here: they become proposals and end the
    turn. Every tool execution (reads included) runs under the actor
    override. The set/reset of that override never straddles a yield
    (Starlette runs each ``next()`` of this generator in a copied
    threadpool context).
    """
    if messages and messages[0].get("role") == "system":
        conversation: list[dict[str, Any]] = list(messages)
    else:
        conversation = [{"role": "system", "content": SYSTEM_PROMPT}, *messages]
    trail: list[dict[str, Any]] = []
    proposals: list[dict[str, Any]] = []

    for _round in range(MAX_ROUNDS):
        content_parts: list[str] = []
        calls: dict[int, dict[str, str]] = {}
        finish_reason: str | None = None

        try:
            for chunk in llm.stream_chat(conversation, tools=tool_schemas()):
                choices = chunk.get("choices")
                if not choices:
                    continue
                choice = choices[0]
                delta = choice.get("delta") or {}
                content = delta.get("content")
                if content:
                    content_parts.append(content)
                    yield {"type": "delta", "text": content}
                for call in delta.get("tool_calls") or []:
                    index = int(call.get("index", 0) or 0)
                    entry = calls.setdefault(
                        index, {"id": "", "name": "", "arguments": ""}
                    )
                    if call.get("id"):
                        entry["id"] = call["id"]
                    function = call.get("function") or {}
                    if function.get("name"):
                        entry["name"] = function["name"]
                    if function.get("arguments"):
                        entry["arguments"] += function["arguments"]
                if choice.get("finish_reason"):
                    finish_reason = choice["finish_reason"]
        except LLMError as exc:
            yield {"type": "error", "detail": str(exc)}
            return

        if finish_reason != "tool_calls" or not calls:
            yield {
                "type": "done",
                "answer": "".join(content_parts),
                "trail": trail,
                "proposals": proposals,
                "messages": conversation,
            }
            return

        # Record the assistant turn (text + tool calls) for the next round.
        conversation.append(
            {
                "role": "assistant",
                "content": "".join(content_parts) or None,
                "tool_calls": [
                    {
                        "id": entry["id"],
                        "type": "function",
                        "function": {
                            "name": entry["name"],
                            "arguments": entry["arguments"],
                        },
                    }
                    for _, entry in sorted(calls.items())
                ],
            }
        )

        # Execute the calls: reads run now; writes become proposals and
        # end the turn (the model continues only after approval).
        tool_events: list[dict[str, Any]] = []
        proposal_events: list[dict[str, Any]] = []
        for index in sorted(calls):
            entry = calls[index]
            name = entry["name"]
            args = _parse_args(entry["arguments"])
            if args is None:
                tool_events.append(
                    {
                        "type": "tool",
                        "tool": name,
                        "args": None,
                        "ok": False,
                        "summary": "invalid JSON arguments",
                    }
                )
                conversation.append(
                    {
                        "role": "tool",
                        "tool_call_id": entry["id"],
                        "content": "Error: invalid JSON arguments",
                    }
                )
                continue
            if name in WRITE_TOOL_NAMES:
                proposal = {"id": f"p{len(proposals) + 1}", "tool": name, "args": args}
                proposals.append(proposal)
                proposal_events.append({"type": "proposal", **proposal})
                conversation.append(
                    {
                        "role": "tool",
                        "tool_call_id": entry["id"],
                        "content": (
                            "PROPOSED: the user must approve before this "
                            "runs. You will not see the result this turn."
                        ),
                    }
                )
                continue
            ok, result = execute_tool(name, args, actor)
            tool_events.append(
                {
                    "type": "tool",
                    "tool": name,
                    "args": args,
                    "ok": ok,
                    "summary": _summarize(ok, result),
                }
            )
            conversation.append(
                {
                    "role": "tool",
                    "tool_call_id": entry["id"],
                    "content": result,
                }
            )

        for event in tool_events:
            trail.append(event)
            yield event
        for event in proposal_events:
            yield event
        if proposal_events:
            yield {
                "type": "done",
                "answer": "".join(content_parts),
                "trail": trail,
                "proposals": proposals,
                "messages": conversation,
            }
            return

    # Iteration cap: the model kept calling tools for MAX_ROUNDS rounds.
    yield {"type": "error", "detail": "tool call limit reached for this turn"}


def status() -> dict[str, Any]:
    """LLM backend status for the chat page (base, model, reachability)."""
    base = llm.api_base()
    try:
        models = llm.list_models()
    except LLMError as exc:
        return {"base": base, "model": None, "reachable": False, "error": str(exc)}
    explicit = os.environ.get("LLM_MODEL", "").strip()
    model = explicit or (models[0] if models else None)
    return {"base": base, "model": model, "reachable": True}
