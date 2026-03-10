from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest


class _FakeSandboxService:
    def __init__(self, roots: dict[str, str] | None = None) -> None:
        self.roots = dict(roots or {})

    def get_session_workspace_path(self, session_id: str) -> str | None:
        return self.roots.get(session_id)


@pytest.mark.asyncio
async def test_path_scope_service_resolves_workspace_root_and_relative_cwd() -> None:
    from tldw_Server_API.app.services.mcp_hub_path_scope_service import McpHubPathScopeService

    workspace_root = "/tmp/mcp-hub-path-scope/project"
    svc = McpHubPathScopeService(sandbox_service=_FakeSandboxService({"sess-1": workspace_root}))
    context = SimpleNamespace(
        session_id="sess-1",
        metadata={"session_id": "sess-1", "workspace_id": "workspace-1", "cwd": "src"},
    )

    result = await svc.resolve_for_context(
        effective_policy={
            "enabled": True,
            "policy_document": {
                "path_scope_mode": "workspace_root",
                "path_scope_enforcement": "approval_required_when_unenforceable",
            },
        },
        context=context,
    )

    assert result["enabled"] is True
    assert result["path_scope_mode"] == "workspace_root"
    assert result["workspace_root"] == str(Path(workspace_root).resolve())
    assert result["cwd"] == str((Path(workspace_root) / "src").resolve())
    assert result["reason"] is None


@pytest.mark.asyncio
async def test_path_scope_service_rejects_cwd_outside_workspace_root() -> None:
    from tldw_Server_API.app.services.mcp_hub_path_scope_service import McpHubPathScopeService

    workspace_root = "/tmp/mcp-hub-path-scope/project"
    svc = McpHubPathScopeService(sandbox_service=_FakeSandboxService({"sess-1": workspace_root}))
    context = SimpleNamespace(
        session_id="sess-1",
        metadata={"session_id": "sess-1", "workspace_id": "workspace-1", "cwd": "/tmp/elsewhere"},
    )

    result = await svc.resolve_for_context(
        effective_policy={
            "enabled": True,
            "policy_document": {
                "path_scope_mode": "cwd_descendants",
                "path_scope_enforcement": "approval_required_when_unenforceable",
            },
        },
        context=context,
    )

    assert result["enabled"] is True
    assert result["workspace_root"] == str(Path(workspace_root).resolve())
    assert result["cwd"] is None
    assert result["reason"] == "cwd_outside_workspace_scope"


@pytest.mark.asyncio
async def test_path_scope_service_returns_workspace_unavailable_without_trusted_root() -> None:
    from tldw_Server_API.app.services.mcp_hub_path_scope_service import McpHubPathScopeService

    svc = McpHubPathScopeService(sandbox_service=_FakeSandboxService({}))
    context = SimpleNamespace(
        session_id="sess-missing",
        metadata={"session_id": "sess-missing", "workspace_id": "workspace-1", "cwd": "src"},
    )

    result = await svc.resolve_for_context(
        effective_policy={
            "enabled": True,
            "policy_document": {
                "path_scope_mode": "workspace_root",
                "path_scope_enforcement": "approval_required_when_unenforceable",
            },
        },
        context=context,
    )

    assert result["enabled"] is True
    assert result["workspace_root"] is None
    assert result["cwd"] is None
    assert result["reason"] == "workspace_root_unavailable"
