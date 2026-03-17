"""MCPSSETransport — SSE-based MCP transport (stub)."""
from __future__ import annotations

from typing import Any

from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_transport import (
    MCPTransport,
)


class MCPSSETransport(MCPTransport):
    """MCP transport over Server-Sent Events.

    This is currently a stub; all I/O methods raise ``NotImplementedError``.
    """

    def __init__(
        self,
        sse_url: str,
        post_url: str | None = None,
        headers: dict[str, str] | None = None,
        timeout_sec: int = 30,
    ) -> None:
        self._sse_url = sse_url
        self._post_url = post_url
        self._headers = headers
        self._timeout_sec = timeout_sec
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        raise NotImplementedError("MCPSSETransport.connect not yet implemented")

    async def close(self) -> None:
        raise NotImplementedError("MCPSSETransport.close not yet implemented")

    async def list_tools(self) -> list[dict[str, Any]]:
        raise NotImplementedError("MCPSSETransport.list_tools not yet implemented")

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        raise NotImplementedError("MCPSSETransport.call_tool not yet implemented")

    async def health_check(self) -> bool:
        raise NotImplementedError("MCPSSETransport.health_check not yet implemented")
