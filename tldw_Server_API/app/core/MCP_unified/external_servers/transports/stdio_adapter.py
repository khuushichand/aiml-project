"""Stdio transport skeleton for external MCP federation."""

from __future__ import annotations

from typing import Any, Optional

from loguru import logger

from ..config_schema import ExternalMCPServerConfig
from .base import ExternalMCPTransportAdapter, ExternalToolCallResult, ExternalToolDefinition


class StdioExternalMCPAdapter(ExternalMCPTransportAdapter):
    """Starter adapter for stdio-based external MCP servers.

    This is an interface scaffold, not a full process/protocol implementation.
    """

    def __init__(self, server_config: ExternalMCPServerConfig) -> None:
        super().__init__(server_id=server_config.id)
        self.server_config = server_config
        self._connected = False

    @property
    def transport_name(self) -> str:
        return "stdio"

    async def connect(self) -> None:
        """Start and connect to the stdio MCP process.

        TODO: spawn process and implement JSON-RPC framing.
        """

        if self.server_config.stdio is None:
            raise ValueError(f"Missing stdio config for server '{self.server_id}'")
        logger.debug(f"External stdio adapter connect requested for {self.server_id}")
        self._connected = True

    async def close(self) -> None:
        self._connected = False

    async def health_check(self) -> dict[str, bool]:
        return {"configured": self.server_config.stdio is not None, "connected": self._connected}

    async def list_tools(self) -> list[ExternalToolDefinition]:
        raise NotImplementedError("Stdio external tool discovery is not implemented yet")

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: Optional[Any] = None,
    ) -> ExternalToolCallResult:
        raise NotImplementedError("Stdio external tool execution is not implemented yet")
