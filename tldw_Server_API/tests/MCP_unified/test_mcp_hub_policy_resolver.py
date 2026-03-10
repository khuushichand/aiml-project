from __future__ import annotations

import pytest


class _FakeRepo:
    def __init__(self) -> None:
        self.profiles = {
            1: {
                "id": 1,
                "name": "Default Read",
                "policy_document": {
                    "allowed_tools": ["notes.search"],
                    "capabilities": ["filesystem.read"],
                },
            },
            2: {
                "id": 2,
                "name": "Group External",
                "policy_document": {
                    "allowed_tools": ["external.servers.list"],
                    "capabilities": ["network.external"],
                },
            },
        }
        self.assignments = [
            {
                "id": 10,
                "target_type": "default",
                "target_id": None,
                "owner_scope_type": "global",
                "owner_scope_id": None,
                "profile_id": 1,
                "inline_policy_document": {},
                "is_active": True,
            },
            {
                "id": 11,
                "target_type": "group",
                "target_id": "ops",
                "owner_scope_type": "user",
                "owner_scope_id": 7,
                "profile_id": 2,
                "inline_policy_document": {"denied_tools": ["external.tools.refresh"]},
                "is_active": True,
            },
            {
                "id": 12,
                "target_type": "persona",
                "target_id": "researcher",
                "owner_scope_type": "user",
                "owner_scope_id": 7,
                "profile_id": None,
                "inline_policy_document": {
                    "allowed_tools": ["Bash(git *)"],
                    "approval_mode": "ask_every_time",
                },
                "is_active": True,
            },
        ]

    async def list_policy_assignments(
        self,
        *,
        owner_scope_type: str | None = None,
        owner_scope_id: int | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
    ) -> list[dict]:
        rows = list(self.assignments)
        if owner_scope_type is not None:
            rows = [row for row in rows if row["owner_scope_type"] == owner_scope_type]
        if owner_scope_id is not None:
            rows = [row for row in rows if row["owner_scope_id"] == owner_scope_id]
        if target_type is not None:
            rows = [row for row in rows if row["target_type"] == target_type]
        if target_id is not None:
            rows = [row for row in rows if row["target_id"] == target_id]
        return rows

    async def get_permission_profile(self, profile_id: int) -> dict | None:
        return self.profiles.get(profile_id)

    async def get_policy_override_by_assignment(self, assignment_id: int) -> dict | None:
        return None


@pytest.mark.asyncio
async def test_policy_resolver_merges_default_group_and_persona_targets() -> None:
    from tldw_Server_API.app.services.mcp_hub_policy_resolver import McpHubPolicyResolver

    resolver = McpHubPolicyResolver(repo=_FakeRepo())

    policy = await resolver.resolve_for_context(
        user_id=7,
        metadata={
            "mcp_policy_context_enabled": True,
            "group_id": "ops",
            "persona_id": "researcher",
        },
    )

    assert policy["enabled"] is True
    assert policy["allowed_tools"] == [
        "notes.search",
        "external.servers.list",
        "Bash(git *)",
    ]
    assert policy["denied_tools"] == ["external.tools.refresh"]
    assert policy["capabilities"] == ["filesystem.read", "network.external"]
    assert policy["approval_mode"] == "ask_every_time"
    assert [source["assignment_id"] for source in policy["sources"]] == [10, 11, 12]


@pytest.mark.asyncio
async def test_policy_resolver_returns_disabled_policy_when_no_assignments_apply() -> None:
    from tldw_Server_API.app.services.mcp_hub_policy_resolver import McpHubPolicyResolver

    repo = _FakeRepo()
    repo.assignments = []
    resolver = McpHubPolicyResolver(repo=repo)

    policy = await resolver.resolve_for_context(
        user_id=99,
        metadata={"mcp_policy_context_enabled": True, "persona_id": "unknown"},
    )

    assert policy["enabled"] is False
    assert policy["allowed_tools"] == []
    assert policy["denied_tools"] == []
    assert policy["sources"] == []
