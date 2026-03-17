"""MCPStdioTransport — stdio-based MCP transport (stub)."""
from __future__ import annotations

from typing import Any

from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_transport import (
    MCPTransport,
)


class MCPStdioTransport(MCPTransport):
    """MCP transport over stdio (JSON-RPC over stdin/stdout).

    This is currently a stub; all I/O methods raise ``NotImplementedError``.
    """

    def __init__(
        self,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self._command = command
        self._args = args
        self._env = env
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        raise NotImplementedError("MCPStdioTransport.connect not yet implemented")

    async def close(self) -> None:
        raise NotImplementedError("MCPStdioTransport.close not yet implemented")

    async def list_tools(self) -> list[dict[str, Any]]:
        raise NotImplementedError("MCPStdioTransport.list_tools not yet implemented")

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        raise NotImplementedError("MCPStdioTransport.call_tool not yet implemented")

    async def health_check(self) -> bool:
        raise NotImplementedError("MCPStdioTransport.health_check not yet implemented")
