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
        decision: str | None = None,
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
            if decision is not None and str(row.get("decision") or "").strip().lower() != str(decision).strip().lower():
                continue
            if row.get("consumed_at") is not None:
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

    async def consume_active_approval_decision(
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
            if str(row.get("decision") or "").strip().lower() != "approved":
                continue
            if not bool(row.get("consume_on_match")):
                continue
            if row.get("consumed_at") is not None:
                continue
            expires_at = row.get("expires_at")
            if expires_at is not None and expires_at <= current:
                continue
            row["consumed_at"] = current
            return dict(row)
        return None

    async def expire_approval_decision(
        self,
        approval_decision_id: int,
        *,
        expires_at: datetime,
    ) -> dict | None:
        for row in self.decisions:
            if int(row.get("id") or 0) != int(approval_decision_id):
                continue
            row["expires_at"] = expires_at
            return dict(row)
        return None


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


def test_scope_key_for_tool_call_hashes_list_commands_distinctly() -> None:
    from tldw_Server_API.app.services.mcp_hub_approval_service import _scope_key_for_tool_call

    first = _scope_key_for_tool_call("sandbox.run", {"command": ["git", "status"]})
    second = _scope_key_for_tool_call("sandbox.run", {"command": ["git", "log"]})
    repeated = _scope_key_for_tool_call("sandbox.run", {"command": ["git", "status"]})

    assert first.startswith("tool:sandbox.run|args:")
    assert second.startswith("tool:sandbox.run|args:")
    assert first != second
    assert first == repeated


def test_scope_key_for_tool_call_includes_path_scope_context() -> None:
    from tldw_Server_API.app.services.mcp_hub_approval_service import _scope_key_for_tool_call

    first = _scope_key_for_tool_call(
        "files.read",
        {"path": "../README.md"},
        scope_payload={
            "path_scope_mode": "cwd_descendants",
            "workspace_root": "/tmp/project",
            "scope_root": "/tmp/project/src",
            "normalized_paths": ["/tmp/project/README.md"],
            "reason": "path_outside_current_folder_scope",
        },
    )
    second = _scope_key_for_tool_call(
        "files.read",
        {"path": "../README.md"},
        scope_payload={
            "path_scope_mode": "cwd_descendants",
            "workspace_root": "/tmp/project",
            "scope_root": "/tmp/project/src",
            "normalized_paths": ["/tmp/project/docs/README.md"],
            "reason": "path_outside_current_folder_scope",
        },
    )

    assert first.startswith("tool:files.read|args:")
    assert second.startswith("tool:files.read|args:")
    assert first != second


def test_arguments_summary_redacts_sensitive_tool_args() -> None:
    from tldw_Server_API.app.services.mcp_hub_approval_service import _arguments_summary

    summary = _arguments_summary(
        {
            "command": ["python", "script.py"],
            "env": {"API_KEY": "secret-value", "MODE": "dev"},
            "files": [
                {"path": "/tmp/demo.txt", "content_b64": "QUJD"},
                {"path": "/tmp/notes.md", "content_b64": "REVG"},
            ],
            "content_b64": "a" * 512,
            "path": "/workspace/project.txt",
            "description": "x" * 256,
        }
    )

    assert summary["command"] == ["python", "script.py"]
    assert summary["env"] == {"redacted": True, "keys": ["API_KEY", "MODE"]}
    assert summary["files"] == [{"path": "/tmp/demo.txt"}, {"path": "/tmp/notes.md"}]
    assert "content_b64" not in summary
    assert summary["description"].endswith("...")
    assert len(summary["description"]) < 200


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
async def test_approval_service_consumes_single_use_approval_after_first_match() -> None:
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
        expires_at=None,
        consume_on_match=True,
        actor_id=7,
    )

    first_retry = await svc.evaluate_tool_call(
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
    assert first_retry["status"] == "allow"
    assert first_retry["reason"] == "active_approval"

    second_retry = await svc.evaluate_tool_call(
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
    assert second_retry["status"] == "approval_required"


@pytest.mark.asyncio
async def test_approval_service_does_not_reuse_denied_decisions() -> None:
    from tldw_Server_API.app.services.mcp_hub_approval_service import McpHubApprovalService
    from tldw_Server_API.app.services.mcp_hub_approval_service import _scope_key_for_tool_call

    repo = _FakeApprovalRepo()
    svc = McpHubApprovalService(repo=repo)
    context = SimpleNamespace(
        user_id="7",
        session_id="sess-1",
        metadata={"persona_id": "researcher"},
    )

    await repo.create_approval_decision(
        approval_policy_id=1,
        context_key="user:7|group:|persona:researcher",
        conversation_id="sess-1",
        tool_name="Bash",
        scope_key=_scope_key_for_tool_call("Bash", {"command": "git status"}),
        decision="denied",
        expires_at=None,
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

    assert result["status"] == "approval_required"


@pytest.mark.asyncio
async def test_approval_service_forces_path_scope_approval_with_scope_context() -> None:
    from tldw_Server_API.app.services.mcp_hub_approval_service import McpHubApprovalService

    repo = _FakeApprovalRepo()
    svc = McpHubApprovalService(repo=repo)
    context = SimpleNamespace(
        user_id="7",
        session_id="sess-1",
        metadata={"persona_id": "researcher"},
    )
    scope_payload = {
        "path_scope_mode": "cwd_descendants",
        "workspace_root": "/tmp/project",
        "scope_root": "/tmp/project/src",
        "normalized_paths": ["/tmp/project/README.md"],
        "reason": "path_outside_current_folder_scope",
    }

    result = await svc.evaluate_tool_call(
        effective_policy={
            "enabled": True,
            "allowed_tools": ["files.read"],
            "approval_policy_id": 1,
        },
        tool_name="files.read",
        tool_args={"path": "../README.md"},
        context=context,
        tool_def={
            "name": "files.read",
            "metadata": {
                "category": "retrieval",
                "uses_filesystem": True,
                "path_boundable": True,
                "path_argument_hints": ["path"],
            },
        },
        is_write=False,
        within_effective_policy=True,
        force_approval=True,
        approval_reason="path_outside_current_folder_scope",
        scope_payload=scope_payload,
    )

    assert result["status"] == "approval_required"
    assert result["approval"]["reason"] == "path_outside_current_folder_scope"
    assert result["approval"]["scope_context"] == scope_payload


@pytest.mark.asyncio
async def test_approval_service_prefers_active_session_approval_over_newer_denial() -> None:
    from tldw_Server_API.app.services.mcp_hub_approval_service import McpHubApprovalService
    from tldw_Server_API.app.services.mcp_hub_approval_service import _scope_key_for_tool_call

    repo = _FakeApprovalRepo()
    svc = McpHubApprovalService(repo=repo)
    context = SimpleNamespace(
        user_id="7",
        session_id="sess-1",
        metadata={"persona_id": "researcher"},
    )
    scope_key = _scope_key_for_tool_call("Bash", {"command": "git status"})

    await repo.create_approval_decision(
        approval_policy_id=1,
        context_key="user:7|group:|persona:researcher",
        conversation_id="sess-1",
        tool_name="Bash",
        scope_key=scope_key,
        decision="approved",
        expires_at=None,
        consume_on_match=False,
        actor_id=7,
    )
    await repo.create_approval_decision(
        approval_policy_id=1,
        context_key="user:7|group:|persona:researcher",
        conversation_id="sess-1",
        tool_name="Bash",
        scope_key=scope_key,
        decision="denied",
        expires_at=None,
        consume_on_match=False,
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
