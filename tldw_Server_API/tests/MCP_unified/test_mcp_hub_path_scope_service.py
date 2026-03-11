from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest


class _FakeSandboxService:
    def __init__(self, roots: dict[str, str] | None = None) -> None:
        self.roots = dict(roots or {})

    def get_session_workspace_path(self, session_id: str) -> str | None:
        return self.roots.get(session_id)


class _FakeWorkspaceRootResolver:
    def __init__(self, result: dict | None = None) -> None:
        self.result = dict(result or {})
        self.calls: list[dict] = []

    async def resolve_for_context(self, **kwargs) -> dict:
        self.calls.append(dict(kwargs))
        return dict(self.result)


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


@pytest.mark.asyncio
async def test_path_scope_service_uses_workspace_id_resolver_for_direct_callers() -> None:
    from tldw_Server_API.app.services.mcp_hub_path_scope_service import McpHubPathScopeService

    resolver = _FakeWorkspaceRootResolver(
        {
            "workspace_root": "/tmp/mcp-hub-path-scope/direct-workspace",
            "workspace_id": "workspace-direct",
            "source": "sandbox_workspace_lookup",
            "reason": None,
        }
    )
    svc = McpHubPathScopeService(
        sandbox_service=_FakeSandboxService({}),
        workspace_root_resolver=resolver,
    )
    context = SimpleNamespace(
        session_id=None,
        user_id="7",
        metadata={"workspace_id": "workspace-direct", "cwd": "src"},
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

    assert result["workspace_root"] == str(Path("/tmp/mcp-hub-path-scope/direct-workspace").resolve())
    assert result["cwd"] == str(Path("/tmp/mcp-hub-path-scope/direct-workspace/src").resolve())
    assert result["reason"] is None
    assert resolver.calls[0]["workspace_id"] == "workspace-direct"
    assert resolver.calls[0]["user_id"] == "7"


@pytest.mark.asyncio
async def test_path_scope_service_fails_closed_for_ambiguous_workspace_id() -> None:
    from tldw_Server_API.app.services.mcp_hub_path_scope_service import McpHubPathScopeService

    resolver = _FakeWorkspaceRootResolver(
        {
            "workspace_root": None,
            "workspace_id": "workspace-direct",
            "source": "sandbox_workspace_lookup",
            "reason": "workspace_root_ambiguous",
        }
    )
    svc = McpHubPathScopeService(
        sandbox_service=_FakeSandboxService({}),
        workspace_root_resolver=resolver,
    )
    context = SimpleNamespace(
        session_id=None,
        user_id="7",
        metadata={"workspace_id": "workspace-direct", "cwd": "src"},
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

    assert result["workspace_root"] is None
    assert result["cwd"] is None
    assert result["reason"] == "workspace_root_ambiguous"


@pytest.mark.asyncio
async def test_path_scope_service_forwards_shared_registry_trust_context() -> None:
    from tldw_Server_API.app.services.mcp_hub_path_scope_service import McpHubPathScopeService

    resolver = _FakeWorkspaceRootResolver(
        {
            "workspace_root": "/srv/shared/docs",
            "workspace_id": "shared-docs",
            "source": "shared_registry",
            "reason": None,
        }
    )
    svc = McpHubPathScopeService(
        sandbox_service=_FakeSandboxService({}),
        workspace_root_resolver=resolver,
    )
    context = SimpleNamespace(
        session_id=None,
        user_id="7",
        metadata={"workspace_id": "shared-docs", "cwd": "docs/api"},
    )

    result = await svc.resolve_for_context(
        effective_policy={
            "enabled": True,
            "selected_workspace_trust_source": "shared_registry",
            "selected_workspace_scope_type": "team",
            "selected_workspace_scope_id": 21,
            "policy_document": {
                "path_scope_mode": "workspace_root",
                "path_scope_enforcement": "approval_required_when_unenforceable",
            },
        },
        context=context,
    )

    assert result["workspace_root"] == str(Path("/srv/shared/docs").resolve())
    assert result["selected_workspace_trust_source"] == "shared_registry"
    assert resolver.calls[0]["workspace_trust_source"] == "shared_registry"
    assert resolver.calls[0]["owner_scope_type"] == "team"
    assert resolver.calls[0]["owner_scope_id"] == 21
