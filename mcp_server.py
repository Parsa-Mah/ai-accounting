"""MCP server entry point.

Usage:
    python mcp_server.py                            # stdio transport (default)
    python mcp_server.py --http [--port 8765]       # streamable HTTP (requires MCP_HTTP_TOKEN)
    python mcp_server.py --print-config lmstudio    # print a ready-to-paste client config
"""

import argparse
import json
import os
import sys

from app.mcp.server import build_server

SERVER_NAME = "accounting"
CLIENTS = (
    "lmstudio",
    "claude-code",
    "claude-desktop",
    "cursor",
    "ollmcp",
    "qwen-code",
    "opencode",
)


def _stdio_command() -> list[str]:
    return [sys.executable or "python", os.path.abspath(__file__)]


def print_config(
    client: str,
    *,
    http: bool = False,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> None:
    """Print a ready-to-paste MCP client config for the given client."""
    if client == "ollmcp":
        print("ollmcp is a command, not a config file:")
        print()
        print("ollmcp mcp add accounting -- " + " ".join(_stdio_command()))
        return

    if http:
        token = os.environ.get("MCP_HTTP_TOKEN") or "YOUR_MCP_HTTP_TOKEN"
        url = f"http://{host}:{port}/mcp"
        if client == "opencode":
            config: dict = {
                "mcp": {
                    SERVER_NAME: {
                        "type": "remote",
                        "url": url,
                        "headers": {"Authorization": f"Bearer {token}"},
                        "enabled": True,
                    }
                }
            }
        else:
            config = {
                "mcpServers": {
                    SERVER_NAME: {
                        "url": url,
                        "headers": {"Authorization": f"Bearer {token}"},
                    }
                }
            }
    elif client == "opencode":
        config = {
            "mcp": {
                SERVER_NAME: {
                    "type": "local",
                    "command": _stdio_command(),
                    "enabled": True,
                }
            }
        }
    else:
        command, *args = _stdio_command()
        config = {"mcpServers": {SERVER_NAME: {"command": command, "args": args}}}

    print(json.dumps(config, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Accounting MCP server")
    parser.add_argument(
        "--http", action="store_true", help="serve streamable HTTP instead of stdio"
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="HTTP bind host (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", type=int, default=8765, help="HTTP port (default: 8765)"
    )
    parser.add_argument(
        "--print-config",
        choices=CLIENTS,
        metavar="CLIENT",
        help="print a ready-to-paste client config and exit",
    )
    args = parser.parse_args()

    if args.print_config is not None:
        print_config(args.print_config, http=args.http, host=args.host, port=args.port)
        return

    if args.http:
        token = os.environ.get("MCP_HTTP_TOKEN")
        if not token:
            print(
                "error: --http requires the MCP_HTTP_TOKEN environment variable "
                "(the bearer token remote clients must send)",
                file=sys.stderr,
            )
            raise SystemExit(2)
        mcp = build_server(http_token=token, host=args.host, port=args.port)
        mcp.run("streamable-http", host=args.host, port=args.port)
    else:
        mcp = build_server()
        mcp.run("stdio")


if __name__ == "__main__":
    main()
