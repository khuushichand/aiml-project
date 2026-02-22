from __future__ import annotations

import pytest
from starlette.requests import Request

from tldw_Server_API.app.api.v1.API_Deps import backpressure as bp_mod
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthContext, AuthPrincipal


def _make_principal(
    *,
    is_admin: bool = False,
    roles: list[str] | None = None,
    permissions: list[str] | None = None,
) -> AuthPrincipal:
    return AuthPrincipal(
        kind="user",
        user_id=1,
        api_key_id=None,
        subject=None,
        token_type="access",
        jti=None,
        roles=list(roles or []),
        permissions=list(permissions or []),
        is_admin=is_admin,
        org_ids=[],
        team_ids=[],
    )


def _make_request(principal: AuthPrincipal | None) -> Request:
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})
    if principal is not None:
        request.state.auth = AuthContext(
            principal=principal,
            ip=None,
            user_agent=None,
            request_id=None,
        )
    return request


def _current_user() -> User:
    return User(
        id=1,
        username="legacy-admin",
        email="legacy-admin@example.com",
        is_active=True,
        is_admin=True,
        roles=["user"],
        permissions=[],
    )


@pytest.mark.unit
def test_backpressure_tenant_rps_bypass_honors_admin_role_claim(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(bp_mod, "is_single_user_profile_mode", lambda: True)
    principal = _make_principal(is_admin=False, roles=["admin"], permissions=[])

    assert bp_mod._should_enforce_ingest_tenant_rps(_make_request(principal), _current_user()) is False


@pytest.mark.unit
def test_backpressure_tenant_rps_bypass_honors_system_configure_permission(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(bp_mod, "is_single_user_profile_mode", lambda: True)
    principal = _make_principal(
        is_admin=False,
        roles=["user"],
        permissions=["system.configure"],
    )

    assert bp_mod._should_enforce_ingest_tenant_rps(_make_request(principal), _current_user()) is False


@pytest.mark.unit
def test_backpressure_tenant_rps_does_not_bypass_boolean_admin_without_claims(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(bp_mod, "is_single_user_profile_mode", lambda: True)
    principal = _make_principal(
        is_admin=True,
        roles=["user"],
        permissions=[],
    )

    assert bp_mod._should_enforce_ingest_tenant_rps(_make_request(principal), _current_user()) is True
