from __future__ import annotations

import base64

import pytest
from fastapi import Request

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal
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
        user_id=101,
        api_key_id=None,
        subject="test-admin",
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
def auth_header(auth_headers):
    return auth_headers


@pytest.fixture()
def client(client_user_only, monkeypatch):
    monkeypatch.setenv("BYOK_ENCRYPTION_KEY", _b64_key(b"t"))
    monkeypatch.delenv("BYOK_SECONDARY_ENCRYPTION_KEY", raising=False)
    reset_settings()
    return client_user_only


@pytest.fixture()
def principal_override(client):
    def _install(principal: AuthPrincipal) -> None:
        _override_principal(client, principal)

    yield _install
    client.app.dependency_overrides.pop(get_auth_principal, None)


def test_put_and_get_telegram_bot_config_uses_shared_scope(client, auth_header, principal_override):
    principal = _make_principal(
        active_team_id=22,
        active_org_id=11,
        team_ids=[22, 23],
        org_ids=[11, 12],
    )
    principal_override(principal)

    payload = {
        "bot_token": ":".join(["123", "abc"]),
        "webhook_secret": "-".join(["secret", "123"]),
        "enabled": True,
    }
    put_res = client.put("/api/v1/telegram/admin/bot", json=payload, headers=auth_header)
    assert put_res.status_code == 200
    put_body = put_res.json()
    assert put_body["scope_type"] == "team"
    assert put_body["scope_id"] == 22
    assert put_body["bot_username"] == "example_bot"
    assert put_body["enabled"] is True

    get_res = client.get("/api/v1/telegram/admin/bot", headers=auth_header)
    assert get_res.status_code == 200
    body = get_res.json()
    assert body["scope_type"] == "team"
    assert body["scope_id"] == 22
    assert body["bot_username"] == "example_bot"
    assert body["enabled"] is True


def test_put_telegram_bot_config_rejects_missing_active_scope(client, auth_header, principal_override):
    principal = _make_principal(
        org_ids=[11, 12],
        team_ids=[22],
    )
    principal_override(principal)

    payload = {
        "bot_token": ":".join(["123", "abc"]),
        "webhook_secret": "-".join(["secret", "123"]),
        "enabled": True,
    }
    res = client.put("/api/v1/telegram/admin/bot", json=payload, headers=auth_header)
    assert res.status_code == 400
    assert "active org/team scope" in res.json()["detail"]


@pytest.mark.parametrize(
    ("active_org_id", "active_team_id", "org_ids", "team_ids"),
    [
        (999, None, [11], []),
        (None, 999, [], [22]),
    ],
)
def test_put_telegram_bot_config_rejects_stale_active_scope_claim(
    client,
    auth_header,
    principal_override,
    active_org_id,
    active_team_id,
    org_ids,
    team_ids,
):
    principal = _make_principal(
        active_org_id=active_org_id,
        active_team_id=active_team_id,
        org_ids=org_ids,
        team_ids=team_ids,
    )
    principal_override(principal)

    payload = {
        "bot_token": ":".join(["123", "abc"]),
        "webhook_secret": "-".join(["secret", "123"]),
        "enabled": True,
    }
    res = client.put("/api/v1/telegram/admin/bot", json=payload, headers=auth_header)
    assert res.status_code == 400
    assert "active org/team scope" in res.json()["detail"]


def test_put_telegram_bot_config_rejects_whitespace_credentials(client, auth_header, principal_override):
    principal = _make_principal(active_org_id=11, org_ids=[11], team_ids=[])
    principal_override(principal)

    payload = {
        "bot_token": "   ",
        "webhook_secret": "\t",
        "enabled": True,
    }
    res = client.put("/api/v1/telegram/admin/bot", json=payload, headers=auth_header)
    assert res.status_code == 422
