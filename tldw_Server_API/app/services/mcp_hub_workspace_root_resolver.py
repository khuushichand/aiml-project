from __future__ import annotations

from pathlib import Path
from typing import Any

from tldw_Server_API.app.core.Sandbox.service import SandboxService


def _first_nonempty(*values: Any) -> str | None:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return None


def _normalize_workspace_root(path_value: str) -> str:
    return str(Path(path_value).expanduser().resolve(strict=False))


class McpHubWorkspaceRootResolver:
    """Resolve a trusted workspace root for MCP Hub path-scope enforcement."""

    def __init__(self, sandbox_service: SandboxService | Any | None = None) -> None:
        self._sandbox_service = sandbox_service or SandboxService()

    async def resolve_for_context(
        self,
        *,
        session_id: str | None,
        user_id: str | None,
        workspace_id: str | None,
    ) -> dict[str, Any]:
        session_key = _first_nonempty(session_id)
        user_key = _first_nonempty(user_id)
        workspace_key = _first_nonempty(workspace_id)

        result = {
            "workspace_root": None,
            "workspace_id": workspace_key,
            "source": None,
            "reason": None,
        }

        if session_key:
            workspace_root = self._sandbox_service.get_session_workspace_path(session_key)
            if workspace_root:
                result["workspace_root"] = _normalize_workspace_root(str(workspace_root))
                result["source"] = "sandbox_session"
                return result

        if not user_key or not workspace_key:
            result["reason"] = "workspace_root_unavailable"
            return result

        candidates = self._sandbox_service.list_workspace_paths_for_user_workspace(
            user_id=user_key,
            workspace_id=workspace_key,
        )
        normalized_roots = sorted(
            {
                _normalize_workspace_root(str(path_value))
                for path_value in list(candidates or [])
                if str(path_value or "").strip()
            }
        )
        if not normalized_roots:
            result["reason"] = "workspace_root_unavailable"
            return result
        if len(normalized_roots) > 1:
            result["source"] = "sandbox_workspace_lookup"
            result["reason"] = "workspace_root_ambiguous"
            return result

        result["workspace_root"] = normalized_roots[0]
        result["source"] = "sandbox_workspace_lookup"
        return result
