from __future__ import annotations

import base64

import pytest
from fastapi import Request

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal
from tldw_Server_API.app.api.v1.endpoints.telegram_support import (
    _reset_telegram_webhook_state_for_tests,
)
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthContext, AuthPrincipal
from tldw_Server_API.app.core.AuthNZ.settings import reset_settings


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
        user_id=202,
        api_key_id=None,
        subject="telegram-webhook-test",
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


@pytest.fixture()
def client(client_user_only, monkeypatch):
    monkeypatch.setenv("BYOK_ENABLED", "1")
    monkeypatch.setenv("BYOK_ENCRYPTION_KEY", _b64_key(b"t"))
    monkeypatch.delenv("BYOK_SECONDARY_ENCRYPTION_KEY", raising=False)
    reset_settings()
    _reset_telegram_webhook_state_for_tests()
    return client_user_only


@pytest.fixture()
def principal_override(client):
    def _install(principal: AuthPrincipal) -> None:
        _override_principal(client, principal)

    yield _install
    client.app.dependency_overrides.pop(get_auth_principal, None)
    _reset_telegram_webhook_state_for_tests()


def _seed_telegram_bot(
    client, principal_override, *, scope_type: str, scope_id: int, bot_token: str, webhook_secret: str
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


def test_telegram_webhook_accepts_and_dedupes_replayed_update(client, principal_override):
    _seed_telegram_bot(
        client,
        principal_override,
        scope_type="team",
        scope_id=22,
        bot_token="123:abc",
        webhook_secret="secret-123",
    )

    payload = {
        "update_id": 5001,
        "message": {
            "message_id": 10,
            "chat": {"id": 222, "type": "private"},
            "text": "hello",
        },
    }
    headers = {"X-Telegram-Bot-Api-Secret-Token": "secret-123"}

    first = client.post("/api/v1/telegram/webhook", json=payload, headers=headers)
    second = client.post("/api/v1/telegram/webhook", json=payload, headers=headers)

    assert first.status_code == 200
    assert first.json() == {"ok": True, "status": "accepted"}
    assert second.status_code == 200
    assert second.json() == {"ok": True, "status": "duplicate"}


def test_telegram_webhook_rejects_invalid_secret(client, principal_override):
    _seed_telegram_bot(
        client,
        principal_override,
        scope_type="org",
        scope_id=33,
        bot_token="123:def",
        webhook_secret="secret-456",
    )

    response = client.post(
        "/api/v1/telegram/webhook",
        json={"update_id": 5002, "message": {"message_id": 11, "chat": {"id": 333, "type": "private"}}},
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
    )

    assert response.status_code == 401
    assert response.json()["error"] == "invalid_secret"


def test_telegram_webhook_rejects_malformed_payload(client, principal_override):
    _seed_telegram_bot(
        client,
        principal_override,
        scope_type="team",
        scope_id=44,
        bot_token="123:ghi",
        webhook_secret="secret-789",
    )

    response = client.post(
        "/api/v1/telegram/webhook",
        data="not-json",
        headers={
            "content-type": "application/json",
            "X-Telegram-Bot-Api-Secret-Token": "secret-789",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_json"
