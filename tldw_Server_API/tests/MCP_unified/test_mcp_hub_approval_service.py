from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest


class _FakeApprovalRepo:
    def __init__(self) -> None:
        self.policies = {
            1: {
                "id": 1,
                "name": "Outside Profile",
                "mode": "ask_outside_profile",
                "rules": {"duration_options": ["once", "session"]},
                "is_active": True,
            },
            2: {
                "id": 2,
                "name": "Sensitive Writes",
                "mode": "ask_on_sensitive_actions",
                "rules": {},
                "is_active": True,
            },
        }
        self.decisions: list[dict] = []

    async def get_approval_policy(self, approval_policy_id: int) -> dict | None:
        return self.policies.get(int(approval_policy_id))

    async def find_active_approval_decision(
        self,
        *,
        approval_policy_id: int | None,
        context_key: str,
        conversation_id: str | None,
        tool_name: str,
        scope_key: str,
        now: datetime | None = None,
    ) -> dict | None:
        current = now or datetime.now(timezone.utc)
        for row in reversed(self.decisions):
            if approval_policy_id is not None and int(row.get("approval_policy_id") or 0) != int(approval_policy_id):
                continue
            if row.get("context_key") != context_key:
                continue
            if row.get("conversation_id") != conversation_id:
                continue
            if row.get("tool_name") != tool_name:
                continue
            if row.get("scope_key") != scope_key:
                continue
            expires_at = row.get("expires_at")
            if expires_at is not None and expires_at <= current:
                continue
            return dict(row)
        return None

    async def create_approval_decision(self, **kwargs) -> dict:
        row = {"id": len(self.decisions) + 1, **kwargs}
        self.decisions.append(row)
        return row


@pytest.mark.asyncio
async def test_approval_service_requires_approval_for_outside_profile_call() -> None:
    from tldw_Server_API.app.services.mcp_hub_approval_service import McpHubApprovalService

    svc = McpHubApprovalService(repo=_FakeApprovalRepo())
    context = SimpleNamespace(
        user_id="7",
        session_id="sess-1",
        metadata={"persona_id": "researcher"},
    )

    result = await svc.evaluate_tool_call(
        effective_policy={
            "enabled": True,
            "allowed_tools": ["notes.search"],
            "approval_policy_id": 1,
        },
        tool_name="Bash",
        tool_args={"command": "git status"},
        context=context,
        tool_def={"name": "Bash", "metadata": {"category": "management"}},
        is_write=False,
        within_effective_policy=False,
    )

    assert result["status"] == "approval_required"
    assert result["approval"]["reason"] == "outside_profile"
    assert result["approval"]["tool_name"] == "Bash"
    assert result["approval"]["duration_options"] == ["once", "session"]


@pytest.mark.asyncio
async def test_approval_service_allows_call_with_active_elevation() -> None:
    from tldw_Server_API.app.services.mcp_hub_approval_service import McpHubApprovalService

    repo = _FakeApprovalRepo()
    svc = McpHubApprovalService(repo=repo)
    context = SimpleNamespace(
        user_id="7",
        session_id="sess-1",
        metadata={"persona_id": "researcher"},
    )

    initial = await svc.evaluate_tool_call(
        effective_policy={
            "enabled": True,
            "allowed_tools": ["notes.search"],
            "approval_policy_id": 1,
        },
        tool_name="Bash",
        tool_args={"command": "git status"},
        context=context,
        tool_def={"name": "Bash", "metadata": {"category": "management"}},
        is_write=False,
        within_effective_policy=False,
    )
    approval = initial["approval"]

    await svc.record_decision(
        approval_policy_id=1,
        context_key=approval["context_key"],
        conversation_id=approval["conversation_id"],
        tool_name=approval["tool_name"],
        scope_key=approval["scope_key"],
        decision="approved",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        actor_id=7,
    )

    result = await svc.evaluate_tool_call(
        effective_policy={
            "enabled": True,
            "allowed_tools": ["notes.search"],
            "approval_policy_id": 1,
        },
        tool_name="Bash",
        tool_args={"command": "git status"},
        context=context,
        tool_def={"name": "Bash", "metadata": {"category": "management"}},
        is_write=False,
        within_effective_policy=False,
    )

    assert result["status"] == "allow"
    assert result["reason"] == "active_approval"


@pytest.mark.asyncio
async def test_approval_service_requires_approval_for_sensitive_write_tool() -> None:
    from tldw_Server_API.app.services.mcp_hub_approval_service import McpHubApprovalService

    svc = McpHubApprovalService(repo=_FakeApprovalRepo())
    context = SimpleNamespace(
        user_id="7",
        session_id="sess-2",
        metadata={"persona_id": "researcher"},
    )

    result = await svc.evaluate_tool_call(
        effective_policy={
            "enabled": True,
            "allowed_tools": ["media.update"],
            "approval_policy_id": 2,
        },
        tool_name="media.update",
        tool_args={"media_id": 1},
        context=context,
        tool_def={"name": "media.update", "metadata": {"category": "management"}},
        is_write=True,
        within_effective_policy=True,
    )

    assert result["status"] == "approval_required"
    assert result["approval"]["reason"] == "sensitive_action"
