from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest


class _FakePathScopeService:
    def __init__(self, result: dict) -> None:
        self.result = dict(result)

    async def resolve_for_context(self, *, effective_policy, context):  # noqa: ANN001
        return dict(self.result)


@pytest.mark.asyncio
async def test_path_enforcement_allows_path_boundable_tool_within_scope() -> None:
    from tldw_Server_API.app.services.mcp_hub_path_enforcement_service import (
        McpHubPathEnforcementService,
    )

    svc = McpHubPathEnforcementService(
        path_scope_service=_FakePathScopeService(
            {
                "enabled": True,
                "path_scope_mode": "workspace_root",
                "path_scope_enforcement": "approval_required_when_unenforceable",
                "workspace_root": "/tmp/mcp-hub-path-enforcer/project",
                "cwd": "/tmp/mcp-hub-path-enforcer/project/src",
                "reason": None,
            }
        )
    )
    workspace_root = "/tmp/mcp-hub-path-enforcer/project"
    cwd_root = str((Path(workspace_root).resolve() / "src").resolve())
    expected_path = str((Path(cwd_root) / "docs/readme.md").resolve())

    result = await svc.evaluate_tool_call(
        effective_policy={
            "enabled": True,
            "policy_document": {"path_scope_mode": "workspace_root"},
        },
        context=SimpleNamespace(metadata={"cwd": "src"}),
        tool_name="files.read",
        tool_args={"path": "docs/readme.md"},
        tool_def={
            "name": "files.read",
            "metadata": {
                "uses_filesystem": True,
                "path_boundable": True,
                "path_argument_hints": ["path"],
            },
        },
    )

    assert result["enabled"] is True
    assert result["within_scope"] is True
    assert result["reason"] is None
    assert result["force_approval"] is False
    assert result["normalized_paths"] == [expected_path]
    assert result["scope_payload"] == {
        "path_scope_mode": "workspace_root",
        "workspace_root": workspace_root,
        "scope_root": str(Path(workspace_root).resolve()),
        "normalized_paths": [expected_path],
    }


@pytest.mark.asyncio
async def test_path_enforcement_requires_approval_for_path_outside_cwd_scope() -> None:
    from tldw_Server_API.app.services.mcp_hub_path_enforcement_service import (
        McpHubPathEnforcementService,
    )

    svc = McpHubPathEnforcementService(
        path_scope_service=_FakePathScopeService(
            {
                "enabled": True,
                "path_scope_mode": "cwd_descendants",
                "path_scope_enforcement": "approval_required_when_unenforceable",
                "workspace_root": "/tmp/mcp-hub-path-enforcer/project",
                "cwd": "/tmp/mcp-hub-path-enforcer/project/src",
                "reason": None,
            }
        )
    )
    workspace_root = "/tmp/mcp-hub-path-enforcer/project"
    cwd_root = str((Path(workspace_root).resolve() / "src").resolve())
    expected_path = str((Path(cwd_root) / "../README.md").resolve())

    result = await svc.evaluate_tool_call(
        effective_policy={
            "enabled": True,
            "policy_document": {"path_scope_mode": "cwd_descendants"},
        },
        context=SimpleNamespace(metadata={"cwd": "src"}),
        tool_name="files.read",
        tool_args={"path": "../README.md"},
        tool_def={
            "name": "files.read",
            "metadata": {
                "uses_filesystem": True,
                "path_boundable": True,
                "path_argument_hints": ["path"],
            },
        },
    )

    assert result["enabled"] is True
    assert result["within_scope"] is False
    assert result["reason"] == "path_outside_current_folder_scope"
    assert result["force_approval"] is True
    assert result["normalized_paths"] == [expected_path]
    assert result["scope_payload"] == {
        "path_scope_mode": "cwd_descendants",
        "workspace_root": workspace_root,
        "scope_root": cwd_root,
        "normalized_paths": [expected_path],
        "reason": "path_outside_current_folder_scope",
    }


@pytest.mark.asyncio
async def test_path_enforcement_requires_approval_for_non_path_boundable_filesystem_tool() -> None:
    from tldw_Server_API.app.services.mcp_hub_path_enforcement_service import (
        McpHubPathEnforcementService,
    )

    svc = McpHubPathEnforcementService(
        path_scope_service=_FakePathScopeService(
            {
                "enabled": True,
                "path_scope_mode": "workspace_root",
                "path_scope_enforcement": "approval_required_when_unenforceable",
                "workspace_root": "/tmp/mcp-hub-path-enforcer/project",
                "cwd": "/tmp/mcp-hub-path-enforcer/project",
                "reason": None,
            }
        )
    )
    workspace_root = "/tmp/mcp-hub-path-enforcer/project"

    result = await svc.evaluate_tool_call(
        effective_policy={
            "enabled": True,
            "policy_document": {"path_scope_mode": "workspace_root"},
        },
        context=SimpleNamespace(metadata={}),
        tool_name="sandbox.run",
        tool_args={"files": [{"path": "src/app.py", "content_b64": "QUJD"}]},
        tool_def={
            "name": "sandbox.run",
            "metadata": {
                "uses_filesystem": True,
                "path_boundable": False,
                "path_argument_hints": ["files[].path"],
            },
        },
    )

    assert result["enabled"] is True
    assert result["within_scope"] is False
    assert result["reason"] == "tool_not_path_boundable"
    assert result["force_approval"] is True
    assert result["normalized_paths"] == []
    assert result["scope_payload"] == {
        "path_scope_mode": "workspace_root",
        "workspace_root": workspace_root,
        "scope_root": str(Path(workspace_root).resolve()),
        "reason": "tool_not_path_boundable",
    }


@pytest.mark.asyncio
async def test_path_enforcement_requires_candidate_to_match_allowlist_root() -> None:
    from tldw_Server_API.app.services.mcp_hub_path_enforcement_service import (
        McpHubPathEnforcementService,
    )

    svc = McpHubPathEnforcementService(
        path_scope_service=_FakePathScopeService(
            {
                "enabled": True,
                "path_scope_mode": "workspace_root",
                "path_scope_enforcement": "approval_required_when_unenforceable",
                "workspace_root": "/tmp/mcp-hub-path-enforcer/project",
                "cwd": "/tmp/mcp-hub-path-enforcer/project",
                "reason": None,
            }
        )
    )
    workspace_root = "/tmp/mcp-hub-path-enforcer/project"
    expected_path = str((Path(workspace_root).resolve() / "src2/notes.md").resolve())

    result = await svc.evaluate_tool_call(
        effective_policy={
            "enabled": True,
            "policy_document": {
                "path_scope_mode": "workspace_root",
                "path_allowlist_prefixes": ["src"],
            },
        },
        context=SimpleNamespace(metadata={}),
        tool_name="files.read",
        tool_args={"path": "src2/notes.md"},
        tool_def={
            "name": "files.read",
            "metadata": {
                "uses_filesystem": True,
                "path_boundable": True,
                "path_argument_hints": ["path"],
            },
        },
    )

    assert result["enabled"] is True
    assert result["within_scope"] is False
    assert result["reason"] == "path_outside_allowlist_scope"
    assert result["force_approval"] is True
    assert result["normalized_paths"] == [expected_path]
    assert result["scope_payload"] == {
        "path_scope_mode": "workspace_root",
        "workspace_root": workspace_root,
        "scope_root": str(Path(workspace_root).resolve()),
        "normalized_paths": [expected_path],
        "path_allowlist_prefixes": ["src"],
        "reason": "path_outside_allowlist_scope",
    }


@pytest.mark.asyncio
async def test_path_enforcement_allows_candidate_within_scope_and_allowlist_root() -> None:
    from tldw_Server_API.app.services.mcp_hub_path_enforcement_service import (
        McpHubPathEnforcementService,
    )

    svc = McpHubPathEnforcementService(
        path_scope_service=_FakePathScopeService(
            {
                "enabled": True,
                "path_scope_mode": "workspace_root",
                "path_scope_enforcement": "approval_required_when_unenforceable",
                "workspace_root": "/tmp/mcp-hub-path-enforcer/project",
                "cwd": "/tmp/mcp-hub-path-enforcer/project",
                "reason": None,
            }
        )
    )
    workspace_root = "/tmp/mcp-hub-path-enforcer/project"
    expected_path = str((Path(workspace_root).resolve() / "src/docs/readme.md").resolve())

    result = await svc.evaluate_tool_call(
        effective_policy={
            "enabled": True,
            "policy_document": {
                "path_scope_mode": "workspace_root",
                "path_allowlist_prefixes": ["src"],
            },
        },
        context=SimpleNamespace(metadata={}),
        tool_name="files.read",
        tool_args={"path": "src/docs/readme.md"},
        tool_def={
            "name": "files.read",
            "metadata": {
                "uses_filesystem": True,
                "path_boundable": True,
                "path_argument_hints": ["path"],
            },
        },
    )

    assert result["enabled"] is True
    assert result["within_scope"] is True
    assert result["reason"] is None
    assert result["force_approval"] is False
    assert result["normalized_paths"] == [expected_path]
    assert result["scope_payload"] == {
        "path_scope_mode": "workspace_root",
        "workspace_root": workspace_root,
        "scope_root": str(Path(workspace_root).resolve()),
        "normalized_paths": [expected_path],
        "path_allowlist_prefixes": ["src"],
    }
