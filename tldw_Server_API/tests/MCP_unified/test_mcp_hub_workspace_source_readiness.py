from __future__ import annotations

from pathlib import Path

import pytest

from tldw_Server_API.app.services.mcp_hub_service import McpHubService


class _Repo:
    def __init__(self) -> None:
        self.workspace_sets = {
            51: {
                "id": 51,
                "name": "Overlap Set",
                "owner_scope_type": "user",
                "owner_scope_id": 7,
                "is_active": True,
            },
        }
        self.workspace_set_members = {
            51: [
                {"workspace_set_object_id": 51, "workspace_id": "workspace-alpha"},
                {"workspace_set_object_id": 51, "workspace_id": "workspace-beta"},
            ],
        }
        self.shared_entries = [
            {
                "id": 71,
                "workspace_id": "shared-alpha",
                "display_name": "Shared Alpha",
                "absolute_root": "/srv/shared/repo",
                "owner_scope_type": "team",
                "owner_scope_id": 21,
                "is_active": True,
            },
            {
                "id": 72,
                "workspace_id": "shared-beta",
                "display_name": "Shared Beta",
                "absolute_root": "/srv/shared/repo/docs",
                "owner_scope_type": "team",
                "owner_scope_id": 21,
                "is_active": True,
            },
        ]

    async def get_workspace_set_object(self, workspace_set_object_id: int):
        return self.workspace_sets.get(workspace_set_object_id)

    async def list_workspace_set_members(self, workspace_set_object_id: int):
        return list(self.workspace_set_members.get(workspace_set_object_id, []))

    async def list_shared_workspace_entries(
        self,
        *,
        owner_scope_type: str | None = None,
        owner_scope_id: int | None = None,
        workspace_id: str | None = None,
    ):
        rows = list(self.shared_entries)
        if workspace_id is not None:
            rows = [row for row in rows if str(row.get("workspace_id") or "") == workspace_id]
        if owner_scope_type is not None:
            rows = [row for row in rows if str(row.get("owner_scope_type") or "") == owner_scope_type]
        if owner_scope_type != "global":
            rows = [row for row in rows if owner_scope_id is None or row.get("owner_scope_id") == owner_scope_id]
        return rows

    async def get_shared_workspace_entry(self, shared_workspace_id: int):
        for row in self.shared_entries:
            if int(row.get("id") or 0) == int(shared_workspace_id):
                return dict(row)
        return None


class _Resolver:
    async def resolve_for_context(
        self,
        *,
        session_id: str | None,
        user_id: str | None,
        workspace_id: str | None,
        workspace_trust_source: str | None = None,
        owner_scope_type: str | None = None,
        owner_scope_id: int | None = None,
    ):
        _ = session_id
        _ = user_id
        _ = owner_scope_type
        _ = owner_scope_id
        if workspace_trust_source == "shared_registry":
            mapping = {
                "shared-alpha": "/srv/shared/repo",
                "shared-beta": "/srv/shared/repo/docs",
            }
        else:
            mapping = {
                "workspace-alpha": "/repo",
                "workspace-beta": "/repo/docs",
            }
        root = mapping.get(str(workspace_id or "").strip())
        return {
            "workspace_root": root,
            "workspace_id": workspace_id,
            "source": workspace_trust_source or "user_local",
            "reason": None if root else "workspace_root_unavailable",
        }


@pytest.mark.asyncio
async def test_workspace_set_readiness_summary_reports_overlap_warning():
    service = McpHubService(repo=_Repo())
    service.workspace_root_resolver = _Resolver()

    summary = await service.get_workspace_set_readiness_summary(workspace_set_object_id=51)

    assert summary["is_multi_root_ready"] is False
    assert "multi_root_overlap_warning" in summary["warning_codes"]
    assert summary["conflicting_workspace_ids"] == ["workspace-alpha", "workspace-beta"]
    assert summary["conflicting_workspace_roots"] == [
        str(Path("/repo").resolve(strict=False)),
        str(Path("/repo/docs").resolve(strict=False)),
    ]


@pytest.mark.asyncio
async def test_workspace_set_readiness_summary_reports_unresolved_workspace_warning():
    repo = _Repo()
    repo.workspace_set_members[51] = [
        {"workspace_set_object_id": 51, "workspace_id": "workspace-alpha"},
        {"workspace_set_object_id": 51, "workspace_id": "workspace-missing"},
    ]
    service = McpHubService(repo=repo)
    service.workspace_root_resolver = _Resolver()

    summary = await service.get_workspace_set_readiness_summary(workspace_set_object_id=51)

    assert summary["is_multi_root_ready"] is False
    assert "workspace_unresolvable_warning" in summary["warning_codes"]
    assert summary["unresolved_workspace_ids"] == ["workspace-missing"]


@pytest.mark.asyncio
async def test_shared_workspace_readiness_summary_reports_overlap_against_visible_entries():
    service = McpHubService(repo=_Repo())
    service.workspace_root_resolver = _Resolver()

    summary = await service.get_shared_workspace_readiness_summary(shared_workspace_id=71)

    assert summary["is_multi_root_ready"] is False
    assert "multi_root_overlap_warning" in summary["warning_codes"]
    assert summary["conflicting_workspace_ids"] == ["shared-alpha", "shared-beta"]
