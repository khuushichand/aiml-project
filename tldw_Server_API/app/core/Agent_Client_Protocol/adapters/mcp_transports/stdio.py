"""MCPStdioTransport — stdio-based MCP transport using ACPStdioClient."""
from __future__ import annotations

from contextlib import suppress
from typing import Any

from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_transport import (
    MCPTransport,
)
from tldw_Server_API.app.core.Agent_Client_Protocol.stdio_client import (
    ACPStdioClient,
)


class MCPStdioTransport(MCPTransport):
    """MCP transport over stdio (JSON-RPC over stdin/stdout).

    Wraps :class:`ACPStdioClient` and performs the MCP initialize
    handshake on :meth:`connect`.
    """

    def __init__(
        self,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self._command = command
        self._args = args or []
        self._env = env or {}
        self._client: ACPStdioClient | None = None
        self._connected = False

    def _create_client(self) -> ACPStdioClient:
        """Create a new :class:`ACPStdioClient` instance.

        Extracted as a method so tests can patch it to inject a mock.
        """
        return ACPStdioClient(self._command, self._args, self._env)

    @property
    def is_connected(self) -> bool:
        if not self._connected or self._client is None:
            return False
        return getattr(self._client, "is_running", False)

    async def connect(self) -> None:
        """Start the subprocess and perform the MCP initialize handshake."""
        if self._client is None:
            self._client = self._create_client()
        try:
            await self._client.start()
            await self._client.call("initialize", {
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "tldw_acp_harness", "version": "0.1.0"},
                "capabilities": {},
            })
            await self._client.notify("initialized", {})
            self._connected = True
        except Exception:
            if self._client is not None:
                with suppress(Exception):
                    await self._client.close()
            self._client = None
            self._connected = False
            raise

    async def close(self) -> None:
        """Shut down the subprocess and mark as disconnected."""
        if self._client is not None:
            await self._client.close()
            self._client = None
        self._connected = False

    async def list_tools(self) -> list[dict[str, Any]]:
        """Request the tool list from the MCP server."""
        if not self._connected or self._client is None:
            raise RuntimeError("Not connected")
        resp = await self._client.call("tools/list", {})
        return resp.result.get("tools", []) if resp.result else []

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Invoke a tool on the MCP server."""
        if not self._connected or self._client is None:
            raise RuntimeError("Not connected")
        resp = await self._client.call(
            "tools/call", {"name": tool_name, "arguments": arguments}
        )
        return resp.result if resp.result else {}

    async def health_check(self) -> bool:
        """Return True if the underlying client process is running."""
        return self._client is not None and getattr(self._client, "is_running", False)
