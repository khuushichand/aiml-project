from __future__ import annotations

from pathlib import Path

import pytest


def test_scope_key_for_tool_call_changes_when_workspace_bundle_changes() -> None:
    from tldw_Server_API.app.services.mcp_hub_approval_service import _scope_key_for_tool_call

    workspace_alpha_root = str(Path("/tmp/workspace-alpha").resolve())
    workspace_beta_root = str(Path("/tmp/workspace-beta").resolve())
    workspace_gamma_root = str(Path("/tmp/workspace-gamma").resolve())
    alpha_readme = str((Path(workspace_alpha_root) / "src/README.md").resolve())
    beta_index = str((Path(workspace_beta_root) / "docs/index.md").resolve())

    first = _scope_key_for_tool_call(
        "files.read",
        {"paths": [alpha_readme, beta_index]},
        scope_payload={
            "workspace_bundle_ids": ["workspace-alpha", "workspace-beta"],
            "workspace_bundle_roots": [workspace_alpha_root, workspace_beta_root],
            "normalized_paths": [alpha_readme, beta_index],
            "reason": "path_outside_allowlist_scope",
        },
    )
    second = _scope_key_for_tool_call(
        "files.read",
        {"paths": [alpha_readme, beta_index]},
        scope_payload={
            "workspace_bundle_ids": ["workspace-alpha", "workspace-gamma"],
            "workspace_bundle_roots": [workspace_alpha_root, workspace_gamma_root],
            "normalized_paths": [alpha_readme, beta_index],
            "reason": "path_outside_allowlist_scope",
        },
    )

    assert first.startswith("tool:files.read|args:")
    assert second.startswith("tool:files.read|args:")
    assert first != second


@pytest.mark.asyncio
async def test_multi_root_service_maps_absolute_paths_to_allowed_workspace_bundle() -> None:
    from tldw_Server_API.app.services.mcp_hub_multi_root_path_service import (
        McpHubMultiRootPathService,
    )

    service = McpHubMultiRootPathService(workspace_root_resolver=object())
    workspace_alpha_root = str(Path("/tmp/workspace-alpha").resolve())
    workspace_beta_root = str(Path("/tmp/workspace-beta").resolve())
    alpha_readme = str((Path(workspace_alpha_root) / "src/README.md").resolve())
    beta_index = str((Path(workspace_beta_root) / "docs/index.md").resolve())

    result = await service.resolve_path_bundle(
        raw_paths=[
            alpha_readme,
            beta_index,
        ],
        active_workspace_id="workspace-alpha",
        active_base_path=workspace_alpha_root,
        allowed_workspace_ids=["workspace-alpha", "workspace-beta"],
        workspace_roots_by_id={
            "workspace-alpha": workspace_alpha_root,
            "workspace-beta": workspace_beta_root,
        },
    )

    assert result["ok"] is True
    assert result["workspace_bundle_ids"] == ["workspace-alpha", "workspace-beta"]
    assert result["path_workspace_map"] == {
        alpha_readme: "workspace-alpha",
        beta_index: "workspace-beta",
    }


@pytest.mark.asyncio
async def test_multi_root_service_denies_ambiguous_workspace_match() -> None:
    from tldw_Server_API.app.services.mcp_hub_multi_root_path_service import (
        McpHubMultiRootPathService,
    )

    service = McpHubMultiRootPathService(workspace_root_resolver=object())
    workspace_alpha_root = str(Path("/tmp/workspace-alpha").resolve())
    workspace_alpha_docs_root = str((Path(workspace_alpha_root) / "docs").resolve())
    shared_doc = str((Path(workspace_alpha_docs_root) / "shared.md").resolve())

    result = await service.resolve_path_bundle(
        raw_paths=[shared_doc],
        active_workspace_id="workspace-alpha",
        active_base_path=workspace_alpha_root,
        allowed_workspace_ids=["workspace-alpha", "workspace-alpha-docs"],
        workspace_roots_by_id={
            "workspace-alpha": workspace_alpha_root,
            "workspace-alpha-docs": workspace_alpha_docs_root,
        },
    )

    assert result["ok"] is False
    assert result["reason"] == "path_matches_multiple_workspace_roots"
