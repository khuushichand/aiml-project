from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import Request

import tldw_Server_API.app.api.v1.endpoints.telegram_support as telegram_support
from tldw_Server_API.app.api.v1.endpoints.telegram_support import (
    TelegramScope,
    TelegramWebhookContext,
    _register_telegram_actor_link_for_tests,
    _reset_telegram_approval_state_for_tests,
    _reset_telegram_link_state_for_tests,
    _reset_telegram_webhook_state_for_tests,
    build_telegram_approval_callback_data,
    telegram_webhook_impl,
)
from tldw_Server_API.app.services.mcp_hub_approval_service import _scope_key_for_tool_call


@dataclass
class _RecordedApprovalDecision:
    id: int
    approval_policy_id: int | None
    context_key: str
    conversation_id: str | None
    tool_name: str
    scope_key: str
    decision: str
    consume_on_match: bool
    expires_at: datetime | None
    actor_id: int | None


class _FakeApprovalService:
    def __init__(self) -> None:
        self.recorded: list[_RecordedApprovalDecision] = []

    async def record_decision(
        self,
        *,
        approval_policy_id: int | None,
        context_key: str,
        conversation_id: str | None,
        tool_name: str,
        scope_key: str,
        decision: str,
        consume_on_match: bool = False,
        expires_at: datetime | None = None,
        actor_id: int | None = None,
    ) -> dict[str, object]:
        row = _RecordedApprovalDecision(
            id=len(self.recorded) + 1,
            approval_policy_id=approval_policy_id,
            context_key=context_key,
            conversation_id=conversation_id,
            tool_name=tool_name,
            scope_key=scope_key,
            decision=decision,
            consume_on_match=consume_on_match,
            expires_at=expires_at,
            actor_id=actor_id,
        )
        self.recorded.append(row)
        return {
            "id": row.id,
            "approval_policy_id": row.approval_policy_id,
            "context_key": row.context_key,
            "conversation_id": row.conversation_id,
            "tool_name": row.tool_name,
            "scope_key": row.scope_key,
            "decision": row.decision,
            "consume_on_match": row.consume_on_match,
            "expires_at": row.expires_at,
            "created_by": row.actor_id,
        }


def _build_request(*, update_id: int, telegram_user_id: int, callback_data: str) -> Request:
    body = {
        "update_id": update_id,
        "callback_query": {
            "id": f"cb-{update_id}",
            "from": {"id": telegram_user_id, "is_bot": False, "username": f"user-{telegram_user_id}"},
            "message": {
                "message_id": 21,
                "chat": {"id": -1001, "type": "group"},
            },
            "data": callback_data,
        },
    }
    headers = [
        (b"content-type", b"application/json"),
        (b"x-telegram-bot-api-secret-token", b"secret-123"),
    ]
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/telegram/webhook",
        "query_string": b"",
        "headers": headers,
    }

    async def _receive() -> dict[str, object]:
        return {"type": "http.request", "body": json.dumps(body).encode("utf-8"), "more_body": False}

    return Request(scope, _receive)


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    _reset_telegram_webhook_state_for_tests()
    _reset_telegram_link_state_for_tests()
    _reset_telegram_approval_state_for_tests()


@pytest.mark.asyncio
async def test_telegram_callback_rejects_approval_from_non_initiating_linked_user(monkeypatch):
    _register_telegram_actor_link_for_tests(
        scope_type="group",
        scope_id=88,
        telegram_user_id=303,
        auth_user_id=303,
    )

    async def _fake_get_org_secret_repo() -> object:
        return object()

    async def _fake_resolve_webhook_scope_from_secret(*, repo: object, webhook_secret: str):
        return TelegramWebhookContext(scope=TelegramScope(scope_type="group", scope_id=88), bot_username="example_bot")

    service = _FakeApprovalService()

    async def _fake_get_approval_service() -> _FakeApprovalService:
        return service

    monkeypatch.setattr(telegram_support, "_resolve_webhook_scope_from_secret", _fake_resolve_webhook_scope_from_secret)

    callback_data = build_telegram_approval_callback_data(
        approval_policy_id=17,
        context_key="user:202|group:88|persona:researcher",
        conversation_id="conv-1",
        tool_name="Bash",
        tool_args={"command": "git status"},
        scope=TelegramScope(scope_type="group", scope_id=88),
        initiating_auth_user_id=202,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    request = _build_request(update_id=9001, telegram_user_id=303, callback_data=callback_data)

    response = await telegram_webhook_impl(
        request=request,
        get_org_secret_repo=_fake_get_org_secret_repo,
        get_approval_service=_fake_get_approval_service,
    )

    assert response.status_code == 403
    assert json.loads(response.body)["error"] == "approval_not_authorized"
    assert service.recorded == []


@pytest.mark.asyncio
async def test_telegram_callback_approves_initiating_linked_user_and_is_single_use(monkeypatch):
    _register_telegram_actor_link_for_tests(
        scope_type="group",
        scope_id=88,
        telegram_user_id=202,
        auth_user_id=202,
    )

    async def _fake_get_org_secret_repo() -> object:
        return object()

    async def _fake_resolve_webhook_scope_from_secret(*, repo: object, webhook_secret: str):
        return TelegramWebhookContext(scope=TelegramScope(scope_type="group", scope_id=88), bot_username="example_bot")

    service = _FakeApprovalService()

    async def _fake_get_approval_service() -> _FakeApprovalService:
        return service

    monkeypatch.setattr(telegram_support, "_resolve_webhook_scope_from_secret", _fake_resolve_webhook_scope_from_secret)

    callback_data = build_telegram_approval_callback_data(
        approval_policy_id=17,
        context_key="user:202|group:88|persona:researcher",
        conversation_id="conv-1",
        tool_name="Bash",
        tool_args={"command": "git status"},
        scope=TelegramScope(scope_type="group", scope_id=88),
        initiating_auth_user_id=202,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )

    first = await telegram_webhook_impl(
        request=_build_request(update_id=9003, telegram_user_id=202, callback_data=callback_data),
        get_org_secret_repo=_fake_get_org_secret_repo,
        get_approval_service=_fake_get_approval_service,
    )
    second = await telegram_webhook_impl(
        request=_build_request(update_id=9004, telegram_user_id=202, callback_data=callback_data),
        get_org_secret_repo=_fake_get_org_secret_repo,
        get_approval_service=_fake_get_approval_service,
    )

    assert first.status_code == 200
    assert json.loads(first.body)["status"] == "approved"
    assert len(service.recorded) == 1
    assert service.recorded[0].decision == "approved"
    assert service.recorded[0].consume_on_match is True
    assert service.recorded[0].actor_id == 202
    assert service.recorded[0].scope_key == _scope_key_for_tool_call("Bash", {"command": "git status"})
    assert second.status_code == 409
    assert json.loads(second.body)["error"] == "approval_unavailable"


@pytest.mark.asyncio
async def test_telegram_callback_rejects_scope_mismatch_as_unavailable(monkeypatch):
    _register_telegram_actor_link_for_tests(
        scope_type="group",
        scope_id=88,
        telegram_user_id=202,
        auth_user_id=202,
    )

    async def _fake_get_org_secret_repo() -> object:
        return object()

    async def _fake_resolve_webhook_scope_from_secret(*, repo: object, webhook_secret: str):
        return TelegramWebhookContext(scope=TelegramScope(scope_type="group", scope_id=99), bot_username="example_bot")

    service = _FakeApprovalService()

    async def _fake_get_approval_service() -> _FakeApprovalService:
        return service

    monkeypatch.setattr(telegram_support, "_resolve_webhook_scope_from_secret", _fake_resolve_webhook_scope_from_secret)

    callback_data = build_telegram_approval_callback_data(
        approval_policy_id=17,
        context_key="user:202|group:88|persona:researcher",
        conversation_id="conv-1",
        tool_name="Bash",
        tool_args={"command": "git status --porcelain"},
        scope=TelegramScope(scope_type="group", scope_id=88),
        initiating_auth_user_id=202,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    request = _build_request(update_id=9002, telegram_user_id=202, callback_data=callback_data)

    response = await telegram_webhook_impl(
        request=request,
        get_org_secret_repo=_fake_get_org_secret_repo,
        get_approval_service=_fake_get_approval_service,
    )

    assert response.status_code == 409
    assert json.loads(response.body)["error"] == "approval_unavailable"
    assert service.recorded == []


@pytest.mark.asyncio
async def test_telegram_callback_rejects_expired_approval(monkeypatch):
    _register_telegram_actor_link_for_tests(
        scope_type="group",
        scope_id=88,
        telegram_user_id=202,
        auth_user_id=202,
    )

    async def _fake_get_org_secret_repo() -> object:
        return object()

    async def _fake_resolve_webhook_scope_from_secret(*, repo: object, webhook_secret: str):
        return TelegramWebhookContext(scope=TelegramScope(scope_type="group", scope_id=88), bot_username="example_bot")

    service = _FakeApprovalService()

    async def _fake_get_approval_service() -> _FakeApprovalService:
        return service

    monkeypatch.setattr(telegram_support, "_resolve_webhook_scope_from_secret", _fake_resolve_webhook_scope_from_secret)

    callback_data = build_telegram_approval_callback_data(
        approval_policy_id=17,
        context_key="user:202|group:88|persona:researcher",
        conversation_id="conv-1",
        tool_name="Bash",
        tool_args={"command": "git status"},
        scope=TelegramScope(scope_type="group", scope_id=88),
        initiating_auth_user_id=202,
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )

    response = await telegram_webhook_impl(
        request=_build_request(update_id=9005, telegram_user_id=202, callback_data=callback_data),
        get_org_secret_repo=_fake_get_org_secret_repo,
        get_approval_service=_fake_get_approval_service,
    )

    assert response.status_code == 409
    assert json.loads(response.body)["error"] == "approval_unavailable"
    assert service.recorded == []
