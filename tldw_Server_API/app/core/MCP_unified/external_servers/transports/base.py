"""Transport adapter contracts for external MCP server federation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:  # pragma: no cover
    from tldw_Server_API.app.core.MCP_unified.protocol import RequestContext


@dataclass(slots=True)
class ExternalToolDefinition:
    """Normalized external tool metadata used by federation logic."""

    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=lambda: {"type": "object"})
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExternalToolCallResult:
    """Normalized external tool execution result."""

    content: Any
    is_error: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class BrokeredExternalCredential:
    """Ephemeral per-call auth material resolved outside long-lived adapter state."""

    headers: dict[str, str] = field(default_factory=dict)
    env: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class ExternalMCPTransportAdapter(ABC):
    """Adapter contract for connecting to and invoking external MCP servers."""

    def __init__(self, server_id: str) -> None:
        self.server_id = server_id

    @property
    @abstractmethod
    def transport_name(self) -> str:
        """Human-readable transport name (e.g. websocket/stdio)."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish transport connection/session."""

    @abstractmethod
    async def close(self) -> None:
        """Close any active transport connection/session."""

    @abstractmethod
    async def health_check(self) -> dict[str, bool]:
        """Return quick health indicators for the upstream transport."""

    @abstractmethod
    async def list_tools(self) -> list[ExternalToolDefinition]:
        """Discover external tools and return normalized definitions."""

    @abstractmethod
    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: Optional["RequestContext"] = None,
        runtime_auth: BrokeredExternalCredential | None = None,
    ) -> ExternalToolCallResult:
        """Execute a tool on the external server and normalize the result."""
