"""External transport adapter contracts and starter implementations."""

from __future__ import annotations

from ..config_schema import ExternalMCPServerConfig, ExternalTransportType
from .base import (
    BrokeredExternalCredential,
    ExternalMCPTransportAdapter,
    ExternalToolCallResult,
    ExternalToolDefinition,
)
from .stdio_adapter import StdioExternalMCPAdapter
from .websocket_adapter import WebSocketExternalMCPAdapter


def build_transport_adapter(server: ExternalMCPServerConfig) -> ExternalMCPTransportAdapter:
    """Build a transport adapter for a validated external server config."""

    if server.transport == ExternalTransportType.WEBSOCKET:
        return WebSocketExternalMCPAdapter(server)
    if server.transport == ExternalTransportType.STDIO:
        return StdioExternalMCPAdapter(server)
    raise ValueError(f"Unsupported external transport: {server.transport}")


__all__ = [
    "ExternalMCPTransportAdapter",
    "ExternalToolCallResult",
    "ExternalToolDefinition",
    "BrokeredExternalCredential",
    "StdioExternalMCPAdapter",
    "WebSocketExternalMCPAdapter",
    "build_transport_adapter",
]
