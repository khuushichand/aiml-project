"""
Unified MCP (Model Context Protocol) implementation for tldw_server

This module combines the best features of MCP v1 and v2 with enhanced security,
performance, and production-readiness.
"""

from .auth.authnz_rbac import AuthNZRBAC
from .auth.authnz_rbac import get_rbac_policy as get_authnz_rbac_policy
from .auth.jwt_manager import JWTManager, get_jwt_manager
from .auth.rbac import Permission, RBACPolicy, UserRole, get_rbac_policy
from .config import get_config
from .modules.base import BaseModule, ModuleConfig
from .modules.registry import ModuleRegistry, get_module_registry
from .protocol import MCPProtocol, MCPRequest, MCPResponse
from .server import MCPServer, get_mcp_server, reset_mcp_server

__version__ = "3.0.0"

__all__ = [
    "MCPServer",
    "get_mcp_server",
    "reset_mcp_server",
    "MCPProtocol",
    "MCPRequest",
    "MCPResponse",
    "BaseModule",
    "ModuleConfig",
    "ModuleRegistry",
    "get_module_registry",
    "JWTManager",
    "get_jwt_manager",
    "RBACPolicy",
    "get_rbac_policy",  # Legacy in-memory RBAC helper (used in unit tests)
    # Prefer AuthNZ-backed RBAC in production; legacy in-memory RBAC remains exported for tests
    "get_authnz_rbac_policy",
    "AuthNZRBAC",
    "UserRole",
    "Permission",
    "get_config",
]
