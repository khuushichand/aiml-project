from __future__ import annotations

from datetime import datetime, timezone

import pytest

from tldw_Server_API.app.core.exceptions import BadRequestError


class _FakeRepo:
    def __init__(self) -> None:
        self.created_payloads: list[dict] = []

    async def create_capability_adapter_mapping(self, **kwargs):
        self.created_payloads.append(dict(kwargs))
        return {
            "id": 11,
            "mapping_id": kwargs["mapping_id"],
            "title": kwargs["title"],
            "description": kwargs.get("description"),
            "owner_scope_type": kwargs["owner_scope_type"],
            "owner_scope_id": kwargs.get("owner_scope_id"),
            "capability_name": kwargs["capability_name"],
            "adapter_contract_version": kwargs["adapter_contract_version"],
            "resolved_policy_document": kwargs["resolved_policy_document"],
            "supported_environment_requirements": kwargs["supported_environment_requirements"],
            "is_active": kwargs.get("is_active", True),
            "created_by": kwargs.get("actor_id"),
            "updated_by": kwargs.get("actor_id"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }


class _FakeToolRegistry:
    async def list_entries(self):
        return [
            {
                "tool_name": "web.search",
                "display_name": "Web Search",
                "module": "search",
            },
            {
                "tool_name": "docs.search",
                "display_name": "Docs Search",
                "module": "docs",
            },
        ]

    async def list_modules(self):
        return [
            {
                "module": "search",
                "display_name": "Search",
                "tool_count": 1,
                "risk_summary": {"low": 1, "medium": 0, "high": 0, "unclassified": 0},
                "metadata_warnings": [],
            },
            {
                "module": "docs",
                "display_name": "Docs",
                "tool_count": 1,
                "risk_summary": {"low": 1, "medium": 0, "high": 0, "unclassified": 0},
                "metadata_warnings": [],
            },
        ]


@pytest.mark.asyncio
async def test_preview_mapping_rejects_unknown_tools() -> None:
    from tldw_Server_API.app.services.mcp_hub_capability_adapter_service import (
        McpHubCapabilityAdapterService,
    )

    svc = McpHubCapabilityAdapterService(repo=_FakeRepo(), tool_registry=_FakeToolRegistry())

    with pytest.raises(BadRequestError, match="unknown tool"):
        await svc.preview_mapping(
            mapping_id="research.global",
            owner_scope_type="global",
            owner_scope_id=None,
            capability_name="tool.invoke.research",
            adapter_contract_version=1,
            resolved_policy_document={"allowed_tools": ["missing.tool"]},
            supported_environment_requirements=[],
            title="Research",
            description=None,
            is_active=True,
        )


@pytest.mark.asyncio
async def test_preview_mapping_warns_for_unsupported_environment_requirements() -> None:
    from tldw_Server_API.app.services.mcp_hub_capability_adapter_service import (
        McpHubCapabilityAdapterService,
    )

    svc = McpHubCapabilityAdapterService(repo=_FakeRepo(), tool_registry=_FakeToolRegistry())

    preview = await svc.preview_mapping(
        mapping_id="research.team",
        owner_scope_type="team",
        owner_scope_id=21,
        capability_name="tool.invoke.research",
        adapter_contract_version=1,
        resolved_policy_document={"allowed_tools": ["web.search"]},
        supported_environment_requirements=["workspace_bounded_read", "future.flag"],
        title="Team Research",
        description="Shared research capability mapping",
        is_active=True,
    )

    assert preview["normalized_mapping"]["supported_environment_requirements"] == [
        "workspace_bounded_read"
    ]
    assert preview["warnings"] == [
        "unsupported environment requirement 'future.flag' will be ignored"
    ]
    assert preview["affected_scope_summary"] == {
        "owner_scope_type": "team",
        "owner_scope_id": 21,
        "display_scope": "team:21",
    }


@pytest.mark.asyncio
async def test_create_mapping_uses_normalized_preview_payload() -> None:
    from tldw_Server_API.app.services.mcp_hub_capability_adapter_service import (
        McpHubCapabilityAdapterService,
    )

    repo = _FakeRepo()
    svc = McpHubCapabilityAdapterService(repo=repo, tool_registry=_FakeToolRegistry())

    created = await svc.create_mapping(
        mapping_id="research.global",
        owner_scope_type="global",
        owner_scope_id=None,
        capability_name="tool.invoke.research",
        adapter_contract_version=1,
        resolved_policy_document={"allowed_tools": ["web.search", "web.search"]},
        supported_environment_requirements=["workspace_bounded_read", "workspace_bounded_read"],
        actor_id=7,
        title="Research",
        description="Maps research capability",
        is_active=True,
    )

    assert repo.created_payloads[0]["resolved_policy_document"] == {
        "allowed_tools": ["web.search"]
    }
    assert repo.created_payloads[0]["supported_environment_requirements"] == [
        "workspace_bounded_read"
    ]
    assert created["id"] == 11


@pytest.mark.asyncio
async def test_preview_mapping_expands_module_ids_to_tool_names() -> None:
    from tldw_Server_API.app.services.mcp_hub_capability_adapter_service import (
        McpHubCapabilityAdapterService,
    )

    svc = McpHubCapabilityAdapterService(repo=_FakeRepo(), tool_registry=_FakeToolRegistry())

    preview = await svc.preview_mapping(
        mapping_id="docs.global",
        owner_scope_type="global",
        owner_scope_id=None,
        capability_name="tool.invoke.docs",
        adapter_contract_version=1,
        resolved_policy_document={"module_ids": ["docs"]},
        supported_environment_requirements=[],
        title="Docs",
        description=None,
        is_active=True,
    )

    assert preview["normalized_mapping"]["resolved_policy_document"] == {
        "module_ids": ["docs"],
        "tool_names": ["docs.search"],
    }
