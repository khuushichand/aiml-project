from __future__ import annotations

import base64

import pytest
from fastapi import Request

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal
from tldw_Server_API.app.api.v1.endpoints.telegram_support import (
    _register_telegram_actor_link_for_tests,
    _reset_telegram_link_state_for_tests,
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
        user_id=303,
        api_key_id=None,
        subject="telegram-link-test",
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
    monkeypatch.setenv("BYOK_ENCRYPTION_KEY", _b64_key(b"l"))
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


def test_start_link_creates_pairing_code(client, auth_headers, principal_override):
    principal = _make_principal(
        active_team_id=22,
        active_org_id=11,
        team_ids=[22, 23],
        org_ids=[11, 12],
    )
    principal_override(principal)

    response = client.post("/api/v1/telegram/admin/link/start", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["scope_type"] == "team"
    assert body["scope_id"] == 22
    assert len(body["pairing_code"]) >= 6


def test_unknown_user_is_denied_for_privileged_action(client, principal_override):
    _seed_telegram_bot(
        client,
        principal_override,
        scope_type="team",
        scope_id=22,
        bot_token="123:abc",
        webhook_secret="secret-123",
    )

    response = client.post(
        "/api/v1/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret-123"},
        json={
            "update_id": 7,
            "message": {
                "message_id": 4,
                "chat": {"id": 1, "type": "private"},
                "from": {"id": 99, "username": "unknown"},
                "text": "/persona set analyst",
            },
        },
    )

    assert response.status_code == 403
    assert response.json()["error"] == "account_link_required"


@pytest.mark.parametrize(
    "message_text",
    [
        "/persona  set analyst",
        "/character\tset analyst",
    ],
)
def test_whitespace_variants_are_still_privileged_actions(client, principal_override, message_text):
    _seed_telegram_bot(
        client,
        principal_override,
        scope_type="team",
        scope_id=22,
        bot_token="123:abc",
        webhook_secret="secret-123",
    )

    response = client.post(
        "/api/v1/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret-123"},
        json={
            "update_id": 10,
            "message": {
                "message_id": 7,
                "chat": {"id": 1, "type": "private"},
                "from": {"id": 99, "username": "unknown"},
                "text": message_text,
            },
        },
    )

    assert response.status_code == 403
    assert response.json()["error"] == "account_link_required"


def test_replayed_denied_privileged_action_is_deduped(client, principal_override):
    _seed_telegram_bot(
        client,
        principal_override,
        scope_type="team",
        scope_id=22,
        bot_token="123:abc",
        webhook_secret="secret-123",
    )

    payload = {
        "update_id": 9,
        "message": {
            "message_id": 6,
            "chat": {"id": 1, "type": "private"},
            "from": {"id": 99, "username": "unknown"},
            "text": "/persona set analyst",
        },
    }
    headers = {"X-Telegram-Bot-Api-Secret-Token": "secret-123"}

    first = client.post("/api/v1/telegram/webhook", headers=headers, json=payload)
    second = client.post("/api/v1/telegram/webhook", headers=headers, json=payload)

    assert first.status_code == 403
    assert first.json()["error"] == "account_link_required"
    assert second.status_code == 200
    assert second.json() == {"ok": True, "status": "duplicate"}


def test_linked_user_is_allowed_for_privileged_action(client, principal_override):
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
        telegram_user_id=99,
        auth_user_id=202,
        telegram_username="linked",
    )

    response = client.post(
        "/api/v1/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret-123"},
        json={
            "update_id": 8,
            "message": {
                "message_id": 5,
                "chat": {"id": 1, "type": "private"},
                "from": {"id": 99, "username": "linked"},
                "text": "/persona set analyst",
            },
        },
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "status": "accepted"}
