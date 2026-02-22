"""External MCP federation scaffolding for MCP Unified."""

from .config_schema import (
    ExternalMCPServerConfig,
    ExternalServerRegistryConfig,
    ExternalTransportType,
    load_external_server_registry,
    parse_external_server_registry,
)
from .manager import ExternalServerManager, VirtualExternalTool

__all__ = [
    "ExternalMCPServerConfig",
    "ExternalServerManager",
    "ExternalServerRegistryConfig",
    "ExternalTransportType",
    "VirtualExternalTool",
    "load_external_server_registry",
    "parse_external_server_registry",
]
