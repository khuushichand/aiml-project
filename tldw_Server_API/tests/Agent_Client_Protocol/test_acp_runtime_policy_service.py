from __future__ import annotations

from typing import Any

import pytest

from tldw_Server_API.app.services.admin_acp_sessions_service import (
    SessionRecord,
    SessionTokenUsage,
)


class _StubPolicyResolver:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def resolve_for_context(
        self,
        *,
        user_id: int | str | None,
        metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        self.calls.append({"user_id": user_id, "metadata": dict(metadata or {})})
        if not self._responses:
            raise AssertionError("No stub responses left")
        return self._responses.pop(0)


@pytest.mark.asyncio
async def test_build_snapshot_uses_normalized_context_and_profile_hints():
    from tldw_Server_API.app.services.acp_runtime_policy_service import (
        ACPRuntimePolicyService,
    )

    session = SessionRecord(
        session_id="session-1",
        user_id=42,
        agent_type="codex",
        name="Policy Session",
        cwd="/tmp/project",
        usage=SessionTokenUsage(),
        mcp_servers=[{"name": "filesystem", "type": "stdio"}],
        persona_id="persona-1",
        workspace_id="workspace-1",
        workspace_group_id="group-1",
        scope_snapshot_id="scope-1",
    )
    resolver = _StubPolicyResolver(
        [
            {
                "policy_document": {
                    "allowed_tools": ["web.search"],
                    "denied_tools": ["shell.exec"],
                    "approval_mode": "require_approval",
                    "capabilities": ["tool.invoke.research"],
                },
                "allowed_tools": ["web.search"],
                "denied_tools": ["shell.exec"],
                "sources": [{"source_kind": "profile", "profile_id": 7}],
                "provenance": [{"source_kind": "capability_mapping", "field": "allowed_tools"}],
            }
        ]
    )
    service = ACPRuntimePolicyService(policy_resolver=resolver)

    snapshot = await service.build_snapshot(
        session_record=session,
        user_id=42,
        acp_profile={
            "id": 7,
            "profile": {
                "execution_config": {"sandbox_mode": "workspace-write"},
                "policy_hints": {"tags": ["researcher"]},
            },
        },
        extra_metadata={"team_id": 9, "org_id": 4},
    )

    assert snapshot.context_summary["persona_id"] == "persona-1"
    assert snapshot.execution_config == {"sandbox_mode": "workspace-write"}
    assert snapshot.policy_provenance_summary["source_kinds"] == [
        "capability_mapping",
        "profile",
    ]
    assert snapshot.policy_summary["allowed_tool_count"] == 1
    assert resolver.calls[0]["metadata"]["mcp_policy_context_enabled"] is True
    assert resolver.calls[0]["metadata"]["acp_profile_id"] == 7
    assert resolver.calls[0]["metadata"]["acp_profile_hint_tags"] == ["researcher"]


@pytest.mark.asyncio
async def test_build_snapshot_fingerprint_changes_when_effective_policy_changes():
    from tldw_Server_API.app.services.acp_runtime_policy_service import (
        ACPRuntimePolicyService,
    )

    session = SessionRecord(
        session_id="session-2",
        user_id=7,
        usage=SessionTokenUsage(),
    )
    resolver = _StubPolicyResolver(
        [
            {"policy_document": {"allowed_tools": ["web.search"]}, "sources": [], "provenance": []},
            {"policy_document": {"allowed_tools": ["docs.search"]}, "sources": [], "provenance": []},
        ]
    )
    service = ACPRuntimePolicyService(policy_resolver=resolver)

    first = await service.build_snapshot(session_record=session, user_id=7)
    second = await service.build_snapshot(session_record=session, user_id=7)

    assert first.policy_snapshot_fingerprint != second.policy_snapshot_fingerprint

