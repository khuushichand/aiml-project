from __future__ import annotations

from pathlib import Path

import pytest


class _FakeSandboxService:
    def __init__(
        self,
        *,
        session_roots: dict[str, str] | None = None,
        workspace_paths: dict[tuple[str, str], list[str]] | None = None,
    ) -> None:
        self.session_roots = dict(session_roots or {})
        self.workspace_paths = {
            (str(user_id), str(workspace_id)): list(paths)
            for (user_id, workspace_id), paths in dict(workspace_paths or {}).items()
        }

    def get_session_workspace_path(self, session_id: str) -> str | None:
        return self.session_roots.get(session_id)

    def list_workspace_paths_for_user_workspace(self, *, user_id: str, workspace_id: str) -> list[str]:
        return list(self.workspace_paths.get((str(user_id), str(workspace_id)), []))


@pytest.mark.asyncio
async def test_workspace_root_resolver_prefers_session_root() -> None:
    from tldw_Server_API.app.services.mcp_hub_workspace_root_resolver import (
        McpHubWorkspaceRootResolver,
    )

    resolver = McpHubWorkspaceRootResolver(
        sandbox_service=_FakeSandboxService(
            session_roots={"sess-1": "/tmp/mcp-hub-workspace/session-root"},
            workspace_paths={("7", "workspace-direct"): ["/tmp/mcp-hub-workspace/direct-root"]},
        )
    )

    result = await resolver.resolve_for_context(
        session_id="sess-1",
        user_id="7",
        workspace_id="workspace-direct",
    )

    assert result["workspace_root"] == str(Path("/tmp/mcp-hub-workspace/session-root").resolve())
    assert result["source"] == "sandbox_session"
    assert result["reason"] is None


@pytest.mark.asyncio
async def test_workspace_root_resolver_resolves_direct_workspace_id_for_user() -> None:
    from tldw_Server_API.app.services.mcp_hub_workspace_root_resolver import (
        McpHubWorkspaceRootResolver,
    )

    resolver = McpHubWorkspaceRootResolver(
        sandbox_service=_FakeSandboxService(
            workspace_paths={("7", "workspace-direct"): ["/tmp/mcp-hub-workspace/direct-root"]}
        )
    )

    result = await resolver.resolve_for_context(
        session_id=None,
        user_id="7",
        workspace_id="workspace-direct",
    )

    assert result["workspace_root"] == str(Path("/tmp/mcp-hub-workspace/direct-root").resolve())
    assert result["source"] == "sandbox_workspace_lookup"
    assert result["reason"] is None


@pytest.mark.asyncio
async def test_workspace_root_resolver_fails_closed_for_ambiguous_workspace_id() -> None:
    from tldw_Server_API.app.services.mcp_hub_workspace_root_resolver import (
        McpHubWorkspaceRootResolver,
    )

    resolver = McpHubWorkspaceRootResolver(
        sandbox_service=_FakeSandboxService(
            workspace_paths={
                ("7", "workspace-direct"): [
                    "/tmp/mcp-hub-workspace/direct-root-a",
                    "/tmp/mcp-hub-workspace/direct-root-b",
                ]
            }
        )
    )

    result = await resolver.resolve_for_context(
        session_id=None,
        user_id="7",
        workspace_id="workspace-direct",
    )

    assert result["workspace_root"] is None
    assert result["reason"] == "workspace_root_ambiguous"
