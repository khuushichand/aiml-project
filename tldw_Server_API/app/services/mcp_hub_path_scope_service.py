from __future__ import annotations

from pathlib import Path
from typing import Any

from tldw_Server_API.app.core.Sandbox.service import SandboxService
from tldw_Server_API.app.services.mcp_hub_workspace_root_resolver import (
    McpHubWorkspaceRootResolver,
)

_DEFAULT_PATH_SCOPE_ENFORCEMENT = "approval_required_when_unenforceable"


def _context_metadata(context: Any | None) -> dict[str, Any]:
    metadata = getattr(context, "metadata", None)
    return dict(metadata) if isinstance(metadata, dict) else {}


def _first_nonempty(*values: Any) -> str | None:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return None


def _normalize_path(value: str, *, workspace_root: Path) -> Path:
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = workspace_root / candidate
    return candidate.resolve(strict=False)


def _is_within(root: Path, candidate: Path) -> bool:
    return candidate == root or root in candidate.parents


class McpHubPathScopeService:
    """Resolve a trusted local path scope for MCP Hub runtime evaluation."""

    def __init__(
        self,
        sandbox_service: SandboxService | Any | None = None,
        workspace_root_resolver: McpHubWorkspaceRootResolver | Any | None = None,
    ) -> None:
        self._sandbox_service = sandbox_service or SandboxService()
        self._workspace_root_resolver = (
            workspace_root_resolver
            or McpHubWorkspaceRootResolver(sandbox_service=self._sandbox_service)
        )

    async def resolve_for_context(
        self,
        *,
        effective_policy: dict[str, Any] | None,
        context: Any | None,
    ) -> dict[str, Any]:
        policy = dict(effective_policy or {})
        policy_document = dict(policy.get("policy_document") or {})
        metadata = _context_metadata(context)
        session_id = _first_nonempty(
            getattr(context, "session_id", None),
            metadata.get("session_id"),
        )
        user_id = _first_nonempty(
            getattr(context, "user_id", None),
            metadata.get("user_id"),
        )
        workspace_id = _first_nonempty(metadata.get("workspace_id"))
        path_scope_mode = _first_nonempty(policy_document.get("path_scope_mode")) or "none"
        path_scope_enforcement = (
            _first_nonempty(policy_document.get("path_scope_enforcement"))
            or _DEFAULT_PATH_SCOPE_ENFORCEMENT
        )
        workspace_trust_source = _first_nonempty(policy.get("selected_workspace_trust_source")) or "user_local"

        result = {
            "enabled": bool(policy.get("enabled")) and path_scope_mode != "none",
            "path_scope_mode": path_scope_mode,
            "path_scope_enforcement": path_scope_enforcement,
            "session_id": session_id,
            "workspace_id": workspace_id,
            "selected_assignment_id": policy.get("selected_assignment_id"),
            "selected_workspace_source_mode": _first_nonempty(policy.get("selected_workspace_source_mode")),
            "selected_workspace_trust_source": workspace_trust_source,
            "selected_workspace_scope_type": _first_nonempty(policy.get("selected_workspace_scope_type")),
            "selected_workspace_scope_id": policy.get("selected_workspace_scope_id"),
            "workspace_root": None,
            "cwd": None,
            "reason": None,
        }
        if not result["enabled"]:
            return result

        workspace_resolution = await self._workspace_root_resolver.resolve_for_context(
            session_id=session_id,
            user_id=user_id,
            workspace_id=workspace_id,
            workspace_trust_source=workspace_trust_source,
            owner_scope_type=_first_nonempty(policy.get("selected_workspace_scope_type")),
            owner_scope_id=policy.get("selected_workspace_scope_id"),
        )
        workspace_root = workspace_resolution.get("workspace_root")
        if workspace_resolution.get("workspace_id") and not result["workspace_id"]:
            result["workspace_id"] = str(workspace_resolution["workspace_id"])
        if workspace_resolution.get("source"):
            result["workspace_root_source"] = str(workspace_resolution["source"])
        if not workspace_root:
            result["reason"] = str(
                workspace_resolution.get("reason") or "workspace_root_unavailable"
            )
            return result

        workspace_root_path = Path(str(workspace_root)).expanduser().resolve(strict=False)
        result["workspace_root"] = str(workspace_root_path)

        cwd_value = _first_nonempty(metadata.get("cwd"))
        if cwd_value:
            cwd_path = _normalize_path(cwd_value, workspace_root=workspace_root_path)
            if not _is_within(workspace_root_path, cwd_path):
                result["reason"] = "cwd_outside_workspace_scope"
                return result
            result["cwd"] = str(cwd_path)
            return result

        if path_scope_mode == "cwd_descendants":
            result["reason"] = "cwd_outside_workspace_scope"
            return result

        return result
