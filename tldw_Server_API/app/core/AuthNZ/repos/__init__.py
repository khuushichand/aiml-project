"""
Repository layer for AuthNZ data access.

This package provides thin, dialect-aware repositories that encapsulate
SQL for core AuthNZ tables (users, api_keys, RBAC) so that higher-level
services like APIKeyManager can remain backend-agnostic.
"""

from tldw_Server_API.app.core.AuthNZ.repos.admin_monitoring_repo import AuthnzAdminMonitoringRepo
from tldw_Server_API.app.core.AuthNZ.repos.mcp_hub_repo import McpHubRepo
from tldw_Server_API.app.core.AuthNZ.repos.workspace_provider_installations_repo import (
    WorkspaceProviderInstallationsRepo,
    get_workspace_provider_installations_repo,
)

__all__ = [
    "AuthnzAdminMonitoringRepo",
    "McpHubRepo",
    "WorkspaceProviderInstallationsRepo",
    "get_workspace_provider_installations_repo",
]
