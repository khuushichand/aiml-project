from __future__ import annotations

import pytest


class _FakeRepo:
    def __init__(self) -> None:
        self.rows = {
            ("global", None, "tool.invoke.research"): {
                "id": 1,
                "mapping_id": "research.global",
                "owner_scope_type": "global",
                "owner_scope_id": None,
                "capability_name": "tool.invoke.research",
                "resolved_policy_document": {"allowed_tools": ["global.search"]},
                "supported_environment_requirements": ["workspace_bounded_read"],
                "is_active": True,
            },
            ("org", 4, "tool.invoke.research"): {
                "id": 2,
                "mapping_id": "research.org.4",
                "owner_scope_type": "org",
                "owner_scope_id": 4,
                "capability_name": "tool.invoke.research",
                "resolved_policy_document": {"allowed_tools": ["org.search"]},
                "supported_environment_requirements": ["workspace_bounded_read"],
                "is_active": True,
            },
            ("team", 9, "tool.invoke.research"): {
                "id": 3,
                "mapping_id": "research.team.9",
                "owner_scope_type": "team",
                "owner_scope_id": 9,
                "capability_name": "tool.invoke.research",
                "resolved_policy_document": {"allowed_tools": ["team.search"]},
                "supported_environment_requirements": ["workspace_bounded_read"],
                "is_active": True,
            },
            ("org", 4, "tool.invoke.notes"): {
                "id": 4,
                "mapping_id": "notes.org.4",
                "owner_scope_type": "org",
                "owner_scope_id": 4,
                "capability_name": "tool.invoke.notes",
                "resolved_policy_document": {
                    "allowed_tools": ["notes.search", "notes.search"],
                    "tool_patterns": ["notes.*"],
                },
                "supported_environment_requirements": ["workspace_bounded_read", "future.flag"],
                "is_active": True,
            },
            ("org", 4, "tool.invoke.docs"): {
                "id": 5,
                "mapping_id": "docs.org.4",
                "owner_scope_type": "org",
                "owner_scope_id": 4,
                "capability_name": "tool.invoke.docs",
                "resolved_policy_document": {
                    "module_ids": ["docs"],
                    "tool_names": ["docs.search"],
                },
                "supported_environment_requirements": [],
                "is_active": True,
            },
            ("org", 4, "tool.invoke.search"): {
                "id": 6,
                "mapping_id": "search.org.4",
                "owner_scope_type": "org",
                "owner_scope_id": 4,
                "capability_name": "tool.invoke.search",
                "resolved_policy_document": {
                    "module_ids": ["search"],
                    "tool_names": ["web.search"],
                },
                "supported_environment_requirements": [],
                "is_active": True,
            },
        }

    async def find_active_capability_mapping(
        self,
        *,
        owner_scope_type: str,
        owner_scope_id: int | None,
        capability_name: str,
    ):
        return self.rows.get((owner_scope_type, owner_scope_id, capability_name))


@pytest.mark.asyncio
async def test_resolution_prefers_team_mapping_over_org_and_global() -> None:
    from tldw_Server_API.app.services.mcp_hub_capability_resolution_service import (
        McpHubCapabilityResolutionService,
    )

    service = McpHubCapabilityResolutionService(repo=_FakeRepo())

    result = await service.resolve_capabilities(
        capability_names=["tool.invoke.research"],
        metadata={"team_id": 9, "org_id": 4},
    )

    assert result.resolved_capabilities == ["tool.invoke.research"]
    assert result.unresolved_capabilities == []
    assert result.resolved_policy_document["allowed_tools"] == ["team.search"]
    assert result.mapping_summaries[0]["mapping_scope_type"] == "team"
    assert result.mapping_summaries[0]["mapping_scope_id"] == 9


@pytest.mark.asyncio
async def test_user_scoped_runtime_context_still_resolves_through_org_then_global() -> None:
    from tldw_Server_API.app.services.mcp_hub_capability_resolution_service import (
        McpHubCapabilityResolutionService,
    )

    service = McpHubCapabilityResolutionService(repo=_FakeRepo())

    result = await service.resolve_capabilities(
        capability_names=["tool.invoke.research"],
        metadata={"user_id": 7, "org_id": 4},
    )

    assert result.resolved_capabilities == ["tool.invoke.research"]
    assert result.resolved_policy_document["allowed_tools"] == ["org.search"]
    assert result.mapping_summaries[0]["mapping_scope_type"] == "org"
    assert result.mapping_summaries[0]["mapping_scope_id"] == 4


@pytest.mark.asyncio
async def test_resolution_reports_unresolved_capabilities_dedupes_effects_and_tracks_requirement_support() -> None:
    from tldw_Server_API.app.services.mcp_hub_capability_resolution_service import (
        McpHubCapabilityResolutionService,
    )

    service = McpHubCapabilityResolutionService(repo=_FakeRepo())

    result = await service.resolve_capabilities(
        capability_names=[
            "tool.invoke.notes",
            "tool.invoke.missing",
            "tool.invoke.notes",
        ],
        metadata={"org_id": 4},
    )

    assert result.resolved_capabilities == ["tool.invoke.notes"]
    assert result.unresolved_capabilities == ["tool.invoke.missing"]
    assert result.resolved_policy_document == {
        "allowed_tools": ["notes.search"],
        "tool_patterns": ["notes.*"],
    }
    assert result.supported_environment_requirements == ["workspace_bounded_read"]
    assert result.unsupported_environment_requirements == ["future.flag"]
    assert "tool.invoke.missing" in result.warnings[0]


@pytest.mark.asyncio
async def test_resolution_unions_module_ids_across_multiple_capability_mappings() -> None:
    from tldw_Server_API.app.services.mcp_hub_capability_resolution_service import (
        McpHubCapabilityResolutionService,
    )

    service = McpHubCapabilityResolutionService(repo=_FakeRepo())

    result = await service.resolve_capabilities(
        capability_names=["tool.invoke.docs", "tool.invoke.search"],
        metadata={"org_id": 4},
    )

    assert result.resolved_policy_document["module_ids"] == ["docs", "search"]
    assert result.resolved_policy_document["tool_names"] == ["docs.search", "web.search"]
