"""MCP server assembly (Python SDK v2).

``build_server()`` wires the domain services into an MCPServer: read
tools are always registered; write tools only when ``MCP_ALLOW_WRITE=1``
(read at call time, not import time, so tests can toggle it). When
``http_token`` is given, a static bearer-token verifier is wired in for
the streamable-HTTP transport (the token itself comes from the
``MCP_HTTP_TOKEN`` environment variable in the entry point).
"""

import hmac
import os
from typing import Any

from mcp.server import MCPServer
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from pydantic import AnyHttpUrl

from app.database import init_db
from app.mcp import tools

INSTRUCTIONS = (
    "You are assisting with this business's books. Money is integer cents; "
    "every result also carries formatted USD strings (*_usd) you can quote "
    "directly. Account references accept a number ('1000') or a name "
    "('Cash'). Dates are ISO: YYYY-MM-DD; months: YYYY-MM."
)


class StaticTokenVerifier(TokenVerifier):
    """Bearer-token verifier that compares against one fixed expected token."""

    def __init__(self, expected: str) -> None:
        self._expected = expected

    async def verify_token(self, token: str) -> AccessToken | None:
        if hmac.compare_digest(token, self._expected):
            return AccessToken(token=token, client_id="accounting-client", scopes=[])
        return None


def build_server(
    *,
    http_token: str | None = None,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> MCPServer:
    init_db()
    allow_write = os.environ.get("MCP_ALLOW_WRITE") == "1"
    auth_kwargs: dict[str, Any] = {}
    if http_token is not None:
        base_url = f"http://{host}:{port}/mcp"
        auth_kwargs["token_verifier"] = StaticTokenVerifier(http_token)
        auth_kwargs["auth"] = AuthSettings(
            issuer_url=AnyHttpUrl(base_url),
            resource_server_url=AnyHttpUrl(base_url),
            validate_token_resource=False,
        )
    mcp = MCPServer("Accounting", instructions=INSTRUCTIONS, **auth_kwargs)
    for tool in tools.read_tools():
        mcp.tool()(tool)
    if allow_write:
        for tool in tools.write_tools():
            mcp.tool()(tool)
    for uri, name, description, resource in tools.resources():
        mcp.resource(
            uri, name=name, description=description, mime_type="application/json"
        )(resource)
    for prompt in tools.prompts():
        mcp.prompt()(prompt)
    return mcp
