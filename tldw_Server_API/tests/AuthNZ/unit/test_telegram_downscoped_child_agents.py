from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tldw_Server_API.app.services.telegram_execution_identity_service import (
    TelegramExecutionIdentityService,
)


def test_child_agent_identity_is_downscoped() -> None:
    service = TelegramExecutionIdentityService(permission_resolver=lambda _user_id: [])
    now = datetime(2026, 3, 19, 19, 30, tzinfo=timezone.utc)

    parent = service.mint_telegram_identity(
        tenant_id="tenant-a",
        auth_user_id="42",
        permissions=["telegram.reply", "email.read", "email.delete"],
        capability_scopes={
            "tool": ["email.read", "email.delete"],
            "workflow": ["email.summary"],
        },
        allowed_workspace_ids=["workspace-mail"],
        allowed_tool_ids=["email.read", "email.delete"],
        allowed_workflow_ids=["email.summary"],
        request_id="req-parent",
        now=now,
        ttl_seconds=300,
    )

    child = service.mint_child_identity(
        parent,
        permissions=["telegram.reply", "email.read", "email.create"],
        capability_scopes={"tool": ["email.read", "email.create"]},
        allowed_workspace_ids=["workspace-mail", "workspace-other"],
        allowed_tool_ids=["email.read", "email.create"],
        now=now + timedelta(seconds=30),
        ttl_seconds=3600,
    )

    assert child.tenant_id == parent.tenant_id
    assert child.auth_user_id == parent.auth_user_id
    assert child.parent_execution_id == parent.execution_id
    assert child.permissions == ["telegram.reply", "email.read"]
    assert child.capability_scopes == {"tool": ["email.read"]}
    assert child.allowed_workspace_ids == ["workspace-mail"]
    assert child.allowed_tool_ids == ["email.read"]
    assert child.allowed_workflow_ids == ["email.summary"]
    assert child.expires_at == parent.expires_at

