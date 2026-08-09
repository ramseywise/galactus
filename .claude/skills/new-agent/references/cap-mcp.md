# cap-mcp — Templates for MCP server/client integration

**Tier: T2 — Runtime-adjacent.** MCP is a transport protocol; server and client scaffolds are portable across runtimes. The runtime determines how tools are registered and invoked (Claude API tool_use, ADK `FunctionDeclaration`, Vercel AI SDK tool), but the MCP server shape is framework-independent.

## Agnostic contract

An agent must be able to expose a set of callable tools over the Model Context Protocol (MCP) transport so that any MCP-compatible client (Claude Desktop, another agent, or an IDE) can discover and invoke them. Symmetrically, an agent must be able to connect to an external MCP server, list its tools, and call them using the same tool-use flow as native tools. The server scaffold (FastMCP) and client scaffold (via Anthropic SDK) below are both portable; the only runtime-coupling is in how the discovered tools are mapped to the host framework's tool registry.

| Runtime | MCP Client Support | Client Mechanism | MCP Server Hosting |
|---|---|---|---|
| Claude API | NATIVE | `client.beta.messages.create(betas=["mcp-client-2025-04-04"])` for remote MCP server tool use | Host a FastMCP server independently; connect via URL or stdio |
| Google ADK | ASSEMBLABLE | `MCPToolset` adapter loads MCP tools into ADK's tool registry | FastMCP server outside ADK |
| LangGraph | ASSEMBLABLE | `langchain_mcp_adapters` maps MCP tools to LangChain tools | FastMCP server outside LangGraph |
| Vercel AI SDK | ASSEMBLABLE | `experimental_createMCPClient` (AI SDK 4+) | FastMCP server as separate process |

> **Security note:** MCP servers that expose filesystem or shell tools MUST validate paths against an allowlist and run in a sandbox. A compromised MCP client sending a malicious tool call should not be able to read `/etc/passwd` or write outside the project root. Apply `agent-safety.md §6` sandboxing rules to any code-execution or filesystem MCP server. OAuth 2.0 with PKCE is the 2025 MCP authentication standard for remote servers — shared-secret is acceptable for local stdio servers only.

## Design notes

- **Server-side**: FastMCP (Python) is the lowest-friction scaffold. Use `@mcp.tool()` decorators; Pydantic models for input schemas. Return strings or dicts — the SDK handles serialization.
- **Client-side**: the `MCPClient` wrapper below handles stdio or SSE transports, tool listing, and dispatching. Inject discovered tools into the host runtime's tool registry.
- **Transport choice**: `stdio` for local dev and IDE integrations; `sse` (SSE/HTTP) for remote production servers. gRPC transport is emerging but not yet widely supported.
- **Tool granularity**: each MCP tool should do one thing. Avoid tools with `action: str` parameters that dispatch internally — the model cannot reason about tool capabilities it cannot see separately.
- **Versioning**: MCP tools are API surfaces. Breaking changes (renamed parameters, changed return shape) require version bumps in the server manifest.

## File: {OUTPUT_DIR}/mcp_server.py

```python
"""FastMCP server scaffold for {AGENT_NAME}.

Exposes the agent's capabilities as MCP tools so any MCP-compatible
client (Claude Desktop, another agent, Cursor, etc.) can discover and
call them without knowing the agent's internal implementation.

Run:
    uv run python -m {AGENT_NAME}.mcp_server           # stdio (default)
    uv run python -m {AGENT_NAME}.mcp_server --transport sse --port 8000

Requires: pip install fastmcp
"""
from __future__ import annotations

import argparse
import logging
from typing import Any

import fastmcp  # pip install fastmcp

logger = logging.getLogger(__name__)

mcp = fastmcp.FastMCP("{AGENT_NAME}")


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------


@mcp.tool()
async def ask(query: str, session_id: str | None = None) -> str:
    """Send a query to {AGENT_NAME} and receive a text response.

    Args:
        query: The user's question or instruction.
        session_id: Optional session identifier for conversation continuity.

    Returns:
        The agent's response as a plain string.
    """
    # Import here to avoid circular imports when server is imported as a module
    from {AGENT_NAME}.main import AgentRunner  # noqa: PLC0415
    import uuid  # noqa: PLC0415

    sid = session_id or str(uuid.uuid4())
    runner = AgentRunner(session_id=sid)
    response = await runner.run(query)
    return response.answer


@mcp.tool()
async def get_status() -> dict[str, Any]:
    """Return the current health and configuration of {AGENT_NAME}.

    Returns:
        Dict with keys: status, version, capabilities.
    """
    return {
        "status": "ok",
        "agent": "{AGENT_NAME}",
        "version": "1.0.0",
        "capabilities": [],  # populate from agent config
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    parser = argparse.ArgumentParser(description="{AGENT_NAME} MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport type (default: stdio for local; sse for remote)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for SSE transport (ignored for stdio)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for SSE transport (use 0.0.0.0 for Docker; never expose without auth)",
    )
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        logger.info("Starting {AGENT_NAME} MCP server on %s:%d (SSE)", args.host, args.port)
        mcp.run(transport="sse", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
```

## File: {OUTPUT_DIR}/mcp_client.py

```python
"""MCP client wrapper for connecting to external MCP servers.

Discovers tools from an MCP server and provides a unified dispatch
interface. Designed to inject discovered tools into any host runtime's
tool registry.

Supports both stdio (local process) and SSE (remote HTTP) transports.

Usage:
    # Stdio (local server process)
    async with MCPClient.stdio(command=["python", "-m", "some_mcp_server"]) as client:
        tools = await client.list_tools()
        result = await client.call_tool("ask", {"query": "hello"})

    # SSE (remote server)
    async with MCPClient.sse(url="http://localhost:8000/sse") as client:
        tools = await client.list_tools()
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

logger = logging.getLogger(__name__)


class MCPClient:
    """Thin wrapper around the MCP client SDK for tool discovery and dispatch.

    Handles connection lifecycle, tool listing, and call dispatch.
    The _client attribute holds the underlying SDK client (mcp.ClientSession).
    """

    def __init__(self, client: Any) -> None:
        self._client = client

    # ------------------------------------------------------------------
    # Factory constructors
    # ------------------------------------------------------------------

    @classmethod
    @asynccontextmanager
    async def stdio(
        cls,
        command: list[str],
        env: dict[str, str] | None = None,
    ) -> AsyncIterator["MCPClient"]:
        """Connect to a local MCP server via stdio transport.

        Args:
            command: Command to launch the MCP server process.
            env: Optional environment variables for the server process.
        """
        try:
            from mcp import ClientSession, StdioServerParameters  # type: ignore[import]
            from mcp.client.stdio import stdio_client  # type: ignore[import]
        except ImportError as exc:
            raise ImportError("mcp is required. Run: pip install mcp") from exc

        params = StdioServerParameters(command=command[0], args=command[1:], env=env)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                logger.info("MCP stdio client connected: %s", command)
                yield cls(session)

    @classmethod
    @asynccontextmanager
    async def sse(cls, url: str, headers: dict[str, str] | None = None) -> AsyncIterator["MCPClient"]:
        """Connect to a remote MCP server via SSE transport.

        Args:
            url: SSE endpoint URL (e.g., http://localhost:8000/sse).
            headers: Optional HTTP headers (e.g., for Bearer auth).
        """
        try:
            from mcp import ClientSession  # type: ignore[import]
            from mcp.client.sse import sse_client  # type: ignore[import]
        except ImportError as exc:
            raise ImportError("mcp is required. Run: pip install mcp") from exc

        async with sse_client(url, headers=headers or {}) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                logger.info("MCP SSE client connected: %s", url)
                yield cls(session)

    # ------------------------------------------------------------------
    # Tool discovery
    # ------------------------------------------------------------------

    async def list_tools(self) -> list[dict[str, Any]]:
        """List all tools available on the connected MCP server.

        Returns:
            List of tool dicts with keys: name, description, inputSchema.
        """
        result = await self._client.list_tools()
        tools = [
            {
                "name": t.name,
                "description": t.description or "",
                "inputSchema": t.inputSchema or {},
            }
            for t in result.tools
        ]
        logger.debug("MCP server tools: %s", [t["name"] for t in tools])
        return tools

    # ------------------------------------------------------------------
    # Tool dispatch
    # ------------------------------------------------------------------

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> Any:
        """Call a tool on the connected MCP server.

        Args:
            tool_name: Name of the tool to call.
            arguments: Input arguments matching the tool's inputSchema.

        Returns:
            The tool's result (string, dict, or list depending on the tool).

        Raises:
            ValueError: If the tool returns an error result.
        """
        args = arguments or {}
        logger.debug("MCP tool call: %s(%s)", tool_name, args)

        result = await self._client.call_tool(tool_name, args)

        if result.isError:
            error_text = " ".join(
                c.text for c in result.content if hasattr(c, "text")
            )
            raise ValueError(f"MCP tool {tool_name!r} returned error: {error_text}")

        # Extract text content from the result
        parts = [c.text for c in result.content if hasattr(c, "text")]
        if len(parts) == 1:
            return parts[0]
        return parts
```
