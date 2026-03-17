"""MCPStreamableHTTPTransport — streamable HTTP MCP transport (stub)."""
from __future__ import annotations

from typing import Any

from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_transport import (
    MCPTransport,
)


class MCPStreamableHTTPTransport(MCPTransport):
    """MCP transport over streamable HTTP (chunked JSON responses).

    This is currently a stub; all I/O methods raise ``NotImplementedError``.
    """

    def __init__(
        self,
        endpoint: str,
        headers: dict[str, str] | None = None,
        timeout_sec: int = 30,
    ) -> None:
        self._endpoint = endpoint
        self._headers = headers
        self._timeout_sec = timeout_sec
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        raise NotImplementedError(
            "MCPStreamableHTTPTransport.connect not yet implemented"
        )

    async def close(self) -> None:
        raise NotImplementedError(
            "MCPStreamableHTTPTransport.close not yet implemented"
        )

    async def list_tools(self) -> list[dict[str, Any]]:
        raise NotImplementedError(
            "MCPStreamableHTTPTransport.list_tools not yet implemented"
        )

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        raise NotImplementedError(
            "MCPStreamableHTTPTransport.call_tool not yet implemented"
        )

    async def health_check(self) -> bool:
        raise NotImplementedError(
            "MCPStreamableHTTPTransport.health_check not yet implemented"
        )
