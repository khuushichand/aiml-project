from __future__ import annotations

import base64
import uuid

import pytest
from fastapi import Request

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal
from tldw_Server_API.app.api.v1.API_Deps.jobs_deps import get_job_manager
from tldw_Server_API.app.api.v1.endpoints.telegram_support import (
    _register_telegram_actor_link_for_tests,
    _reset_telegram_link_state_for_tests,
    _reset_telegram_webhook_state_for_tests,
)
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthContext, AuthPrincipal
from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
from tldw_Server_API.app.core.Jobs.manager import JobManager


def _b64_key(byte_char: bytes) -> str:
    return base64.b64encode(byte_char * 32).decode("ascii")


def _make_principal(
    *,
    active_org_id: int | None = None,
    active_team_id: int | None = None,
    org_ids: list[int] | None = None,
    team_ids: list[int] | None = None,
) -> AuthPrincipal:
    return AuthPrincipal(
        kind="user",
        user_id=404,
        api_key_id=None,
        subject="telegram-job-test",
        token_type="access",
        jti=None,
        roles=["admin"],
        permissions=["system.configure"],
        is_admin=True,
        org_ids=org_ids or [],
        team_ids=team_ids or [],
        active_org_id=active_org_id,
        active_team_id=active_team_id,
    )


def _override_principal(client, principal: AuthPrincipal) -> None:
    async def _fake_get_auth_principal(request: Request) -> AuthPrincipal:
        request.state.auth = AuthContext(principal=principal, ip=None, user_agent=None, request_id=None)
        request.state.active_org_id = principal.active_org_id
        request.state.active_team_id = principal.active_team_id
        return principal

    client.app.dependency_overrides[get_auth_principal] = _fake_get_auth_principal


def _seed_telegram_bot(
    client,
    principal_override,
    *,
    scope_type: str,
    scope_id: int,
    bot_token: str,
    webhook_secret: str,
) -> None:
    if scope_type == "team":
        principal = _make_principal(active_team_id=scope_id, team_ids=[scope_id], org_ids=[1])
    else:
        principal = _make_principal(active_org_id=scope_id, org_ids=[scope_id], team_ids=[1])
    principal_override(principal)

    response = client.put(
        "/api/v1/telegram/admin/bot",
        json={
            "bot_token": bot_token,
            "webhook_secret": webhook_secret,
            "enabled": True,
        },
    )
    assert response.status_code == 200, response.text


@pytest.fixture()
def client(client_user_only, monkeypatch):
    monkeypatch.setenv("BYOK_ENABLED", "1")
    monkeypatch.setenv("BYOK_ENCRYPTION_KEY", _b64_key(b"j"))
    monkeypatch.delenv("BYOK_SECONDARY_ENCRYPTION_KEY", raising=False)
    reset_settings()
    _reset_telegram_webhook_state_for_tests()
    _reset_telegram_link_state_for_tests()
    return client_user_only


@pytest.fixture()
def principal_override(client):
    def _install(principal: AuthPrincipal) -> None:
        _override_principal(client, principal)

    yield _install
    client.app.dependency_overrides.pop(get_auth_principal, None)
    _reset_telegram_webhook_state_for_tests()
    _reset_telegram_link_state_for_tests()


@pytest.fixture()
def job_manager_override(client, tmp_path):
    job_manager = JobManager(tmp_path / "telegram_jobs.db")
    client.app.dependency_overrides[get_job_manager] = lambda: job_manager
    yield job_manager
    client.app.dependency_overrides.pop(get_job_manager, None)


def _post_ask(
    client,
    *,
    update_id: int,
    secret: str,
    telegram_user_id: int,
    text: str = "/ask summarize the last report",
) -> object:
    return client.post(
        "/api/v1/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": secret},
        json={
            "update_id": update_id,
            "message": {
                "message_id": 42,
                "chat": {"id": 100, "type": "private"},
                "from": {"id": telegram_user_id, "username": "linked-user"},
                "text": text,
            },
        },
    )


def test_linked_ask_queues_job_and_returns_queued(client, principal_override, job_manager_override) -> None:
    _seed_telegram_bot(
        client,
        principal_override,
        scope_type="team",
        scope_id=22,
        bot_token="123:abc",
        webhook_secret="secret-123",
    )
    _register_telegram_actor_link_for_tests(
        scope_type="team",
        scope_id=22,
        telegram_user_id=77,
        auth_user_id=901,
    )

    response = _post_ask(client, update_id=12001, secret="secret-123", telegram_user_id=77)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["ok"] is True
    assert payload["status"] == "queued"
    assert payload["request_id"]
    assert uuid.UUID(payload["request_id"])
    assert payload["job_id"] is not None

    job = job_manager_override.get_job(int(payload["job_id"]))
    assert job is not None
    assert job["status"] == "queued"


def test_replayed_linked_ask_is_deduped(client, principal_override, job_manager_override) -> None:
    _seed_telegram_bot(
        client,
        principal_override,
        scope_type="team",
        scope_id=22,
        bot_token="123:abc",
        webhook_secret="secret-123",
    )
    _register_telegram_actor_link_for_tests(
        scope_type="team",
        scope_id=22,
        telegram_user_id=77,
        auth_user_id=901,
    )

    first = _post_ask(client, update_id=12002, secret="secret-123", telegram_user_id=77)
    second = _post_ask(client, update_id=12002, secret="secret-123", telegram_user_id=77)

    assert first.status_code == 200, first.text
    assert first.json()["status"] == "queued"
    assert second.status_code == 200, second.text
    assert second.json() == {"ok": True, "status": "duplicate"}


def test_linked_ask_job_payload_includes_owner_and_session_mapping(
    client,
    principal_override,
    job_manager_override,
) -> None:
    _seed_telegram_bot(
        client,
        principal_override,
        scope_type="team",
        scope_id=22,
        bot_token="123:abc",
        webhook_secret="secret-123",
    )
    _register_telegram_actor_link_for_tests(
        scope_type="team",
        scope_id=22,
        telegram_user_id=77,
        auth_user_id=901,
    )

    response = _post_ask(client, update_id=12003, secret="secret-123", telegram_user_id=77)

    assert response.status_code == 200, response.text
    body = response.json()
    job = job_manager_override.get_job(int(body["job_id"]))
    assert job is not None
    assert job["owner_user_id"] == "901"

    telegram_payload = job["payload"]["telegram"]
    session_payload = job["payload"]["session"]
    assert telegram_payload["scope_type"] == "team"
    assert telegram_payload["scope_id"] == 22
    assert telegram_payload["update_id"] == 12003
    assert telegram_payload["message_id"] == 42
    assert telegram_payload["chat_type"] == "private"
    assert telegram_payload["telegram_user_id"] == 77
    assert telegram_payload["linked_actor"]["auth_user_id"] == "901"
    assert session_payload["tenant_id"] == "team:22"
    assert session_payload["session_key"] == "team:22:dm:77"
    assert uuid.UUID(session_payload["assistant_conversation_id"])
