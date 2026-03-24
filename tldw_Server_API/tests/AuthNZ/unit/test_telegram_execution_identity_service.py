from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tldw_Server_API.app.core.AuthNZ.permissions import TELEGRAM_RECEIVE, TELEGRAM_REPLY
from tldw_Server_API.app.services.telegram_execution_identity_service import (
    TelegramExecutionIdentityService,
)


def test_mint_telegram_identity_adds_transport_permissions_and_fails_closed_on_workspace_scope() -> None:
    captured: dict[str, int | None] = {"user_id": None}

    def _resolve_permissions(user_id: int) -> list[str]:
        captured["user_id"] = user_id
        return ["email.read", "email.read", "email.delete", " "]

    service = TelegramExecutionIdentityService(
        permission_resolver=_resolve_permissions,
        default_ttl_seconds=600,
    )
    now = datetime(2026, 3, 19, 19, 0, tzinfo=timezone.utc)

    identity = service.mint_telegram_identity(
        tenant_id="team:22",
        auth_user_id="42",
        telegram_user_id=77,
        telegram_chat_id=100,
        telegram_thread_id=None,
        scope_type="team",
        scope_id=22,
        request_id="req-telegram-1",
        conversation_id="conv-123",
        now=now,
    )

    assert captured["user_id"] == 42
    assert identity.source == "telegram"
    assert identity.tenant_id == "team:22"
    assert identity.auth_user_id == "42"
    assert identity.request_id == "req-telegram-1"
    assert identity.conversation_id == "conv-123"
    assert identity.permissions == [TELEGRAM_RECEIVE, TELEGRAM_REPLY, "email.read", "email.delete"]
    assert identity.capability_scopes == {}
    assert identity.allowed_workspace_ids == []
    assert identity.allowed_tool_ids == []
    assert identity.allowed_workflow_ids == []
    assert identity.parent_execution_id is None

    payload = identity.to_payload()
    assert payload["issued_at"] == now.isoformat()
    assert payload["expires_at"] == (now + timedelta(seconds=600)).isoformat()

