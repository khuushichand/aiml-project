"""Sharing module: workspace sharing, share tokens, audit, clone, and deletion hooks."""

from tldw_Server_API.app.core.Sharing.share_audit_service import ShareAuditService
from tldw_Server_API.app.core.Sharing.share_token_service import ShareTokenService
from tldw_Server_API.app.core.Sharing.shared_workspace_resolver import (
    SharedWorkspaceContext,
    SharedWorkspaceDBResolver,
)
from tldw_Server_API.app.core.Sharing.workspace_deletion_hook import on_workspace_deleted

try:
    from tldw_Server_API.app.core.Sharing.clone_service import CloneService
except ModuleNotFoundError as exc:  # pragma: no cover - optional until clone service lands
    if exc.name != "tldw_Server_API.app.core.Sharing.clone_service":
        raise
    CloneService = None  # type: ignore[assignment]

__all__ = [
    "ShareTokenService",
    "ShareAuditService",
    "SharedWorkspaceContext",
    "SharedWorkspaceDBResolver",
    "on_workspace_deleted",
]

if CloneService is not None:
    __all__.append("CloneService")
