"""Tests for the AI command center tool bridge (app/services/ai_chat.py).

Covers the OpenAI schema conversion, tool dispatch (reads and writes),
the ``ai:command-center`` actor override, and the ``build_server``
``allow_write`` parameter.
"""

from app.database import SessionLocal
from app.mcp import context, tools
from app.mcp.server import build_server
from app.models.audit import AuditLog
from app.services import ai_chat, audit as audit_service


# --- schemas ---------------------------------------------------------------


def test_tool_schemas_returns_all_50_in_openai_format():
    schemas = ai_chat.tool_schemas()
    assert len(schemas) == 50
    names = {schema["function"]["name"] for schema in schemas}
    expected = {fn.__name__ for fn in [*tools.read_tools(), *tools.write_tools()]}
    assert names == expected
    for schema in schemas:
        assert schema["type"] == "function"
        function = schema["function"]
        assert function["description"]
        assert function["parameters"]["type"] == "object"
        assert "title" not in function["parameters"]  # SDK cosmetic, stripped


def test_tool_schemas_is_cached():
    assert ai_chat.tool_schemas() is ai_chat.tool_schemas()


def test_write_tool_names_covers_all_write_tools():
    expected = {fn.__name__ for fn in tools.write_tools()}
    assert ai_chat.WRITE_TOOL_NAMES == expected
    assert len(ai_chat.WRITE_TOOL_NAMES) == 26


# --- execute_tool ----------------------------------------------------------


def test_execute_read_tool(app_client):
    ok, result = ai_chat.execute_tool(
        "list_accounts", {}, audit_service.AI_COMMAND_CENTER_ACTOR
    )
    assert ok
    assert "Cash" in result


def test_execute_write_tool_audited_as_override_actor(app_client):
    ok, result = ai_chat.execute_tool(
        "create_customer",
        {"name": "Bridge Test Co"},
        audit_service.AI_COMMAND_CENTER_ACTOR,
    )
    assert ok
    assert "Bridge Test Co" in result
    db = SessionLocal()
    rows = (
        db.query(AuditLog)
        .filter_by(actor=audit_service.AI_COMMAND_CENTER_ACTOR)
        .all()
    )
    db.close()
    assert any(row.model == "Customer" for row in rows)


def test_execute_tool_clears_override_afterwards(app_client):
    ok, _ = ai_chat.execute_tool(
        "list_accounts", {}, audit_service.AI_COMMAND_CENTER_ACTOR
    )
    assert ok
    assert audit_service.actor_override() is None


def test_execute_unknown_tool_returns_error_string(app_client):
    ok, result = ai_chat.execute_tool("no_such_tool", {}, "ai:command-center")
    assert not ok
    assert "Unknown tool" in result


def test_execute_bad_args_returns_error_string(app_client):
    ok, result = ai_chat.execute_tool(
        "create_customer", {}, "ai:command-center"
    )
    assert not ok  # missing required 'name' -> TypeError, not an exception
    assert result


def test_execute_tool_domain_error_is_string(app_client):
    ok, result = ai_chat.execute_tool(
        "void_invoice", {"invoice_id": 9999}, "ai:command-center"
    )
    assert not ok
    assert result  # the ToolError message, readable by the LLM


def test_serialize_truncates_oversized_results():
    text = ai_chat._serialize({"data": "x" * 5000})
    assert text.endswith("… (truncated)")
    assert len(text) <= ai_chat._MAX_RESULT_CHARS + len("… (truncated)")


# --- actor override in get_session -----------------------------------------


def test_get_session_honors_actor_override(app_client):
    token = audit_service.set_actor_override(audit_service.AI_COMMAND_CENTER_ACTOR)
    try:
        with context.get_session():
            assert (
                audit_service.current_actor() == audit_service.AI_COMMAND_CENTER_ACTOR
            )
    finally:
        audit_service.reset_actor_override(token)


def test_get_session_without_override_uses_ai_actor(app_client, monkeypatch):
    monkeypatch.setenv("MCP_CLIENT_NAME", "opencode")
    with context.get_session():
        assert audit_service.current_actor() == "ai:opencode"
    monkeypatch.delenv("MCP_CLIENT_NAME")
    with context.get_session():
        assert audit_service.current_actor() == "ai:mcp"  # default client name


# --- build_server allow_write parameter ------------------------------------


def _tool_names(server) -> set[str]:
    return {tool.name for tool in server._tool_manager.list_tools()}


def test_build_server_allow_write_explicit(monkeypatch):
    monkeypatch.delenv("MCP_ALLOW_WRITE", raising=False)
    assert len(_tool_names(build_server(allow_write=True))) == 50
    assert len(_tool_names(build_server(allow_write=False))) == 24


def test_build_server_defaults_to_env(monkeypatch):
    monkeypatch.delenv("MCP_ALLOW_WRITE", raising=False)
    assert len(_tool_names(build_server())) == 24
    monkeypatch.setenv("MCP_ALLOW_WRITE", "1")
    assert len(_tool_names(build_server())) == 50
