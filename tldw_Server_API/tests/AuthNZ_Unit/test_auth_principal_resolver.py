from types import SimpleNamespace
from typing import Any, Dict

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.types import Scope

from tldw_Server_API.app.core.AuthNZ.auth_principal_resolver import get_auth_principal
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthContext, AuthPrincipal
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User


def _make_request(headers: Dict[str, str] | None = None) -> Request:
    scope: Scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in (headers or {}).items()],
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_get_auth_principal_reuses_existing_context():
    req = _make_request()
    principal = AuthPrincipal(kind="anonymous")
    ctx = AuthContext(principal=principal, ip="127.0.0.1", user_agent=None, request_id=None)
    req.state.auth = ctx

    resolved = await get_auth_principal(req)
    assert resolved is principal


@pytest.mark.asyncio
async def test_get_auth_principal_single_user_mode(monkeypatch):
    # Force single-user mode
    fake_settings = SimpleNamespace(PII_REDACT_LOGS=False)

    def _fake_get_settings() -> Any:
        return fake_settings

    def _fake_is_single_user_mode() -> bool:
        return True

    async def _fake_verify_single_user_api_key(request, api_key=None, authorization=None):
        return True

    def _fake_get_single_user_instance() -> User:
        return User(id=1, username="single_user", is_active=True)

    monkeypatch.setattr(
        "tldw_Server_API.app.core.AuthNZ.auth_principal_resolver.get_settings",
        _fake_get_settings,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.AuthNZ.auth_principal_resolver.is_single_user_mode",
        _fake_is_single_user_mode,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.AuthNZ.auth_principal_resolver.verify_single_user_api_key",
        _fake_verify_single_user_api_key,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.AuthNZ.auth_principal_resolver.get_single_user_instance",
        _fake_get_single_user_instance,
    )

    req = _make_request(headers={"X-API-KEY": "fixed-key"})

    principal = await get_auth_principal(req)
    assert principal.kind == "single_user"
    assert principal.user_id == 1
    assert principal.is_admin is True
    assert "admin" in principal.roles
    assert isinstance(getattr(req.state, "auth", None), AuthContext)
    assert getattr(req.state, "user_id", None) == 1


@pytest.mark.asyncio
async def test_get_auth_principal_jwt_path(monkeypatch):
    def _fake_get_settings() -> Any:
        return SimpleNamespace(PII_REDACT_LOGS=False)

    def _fake_is_single_user_mode() -> bool:
        return False

    async def _fake_verify_jwt_and_fetch_user(request, token: str = "") -> User:
        # simulate User with claims and membership already attached to request.state
        request.state.user_id = 42
        request.state.org_ids = [10]
        request.state.team_ids = [20]
        return User(
            id=42,
            username="jwt-user",
            is_active=True,
            roles=["user"],
            permissions=["media.read"],
            is_admin=False,
        )

    monkeypatch.setattr(
        "tldw_Server_API.app.core.AuthNZ.auth_principal_resolver.get_settings",
        _fake_get_settings,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.AuthNZ.auth_principal_resolver.is_single_user_mode",
        _fake_is_single_user_mode,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.AuthNZ.auth_principal_resolver.verify_jwt_and_fetch_user",
        _fake_verify_jwt_and_fetch_user,
    )

    req = _make_request(headers={"Authorization": "Bearer token-abc"})

    principal = await get_auth_principal(req)
    assert principal.kind == "user"
    assert principal.user_id == 42
    assert principal.api_key_id is None
    assert principal.org_ids == [10]
    assert principal.team_ids == [20]


@pytest.mark.asyncio
async def test_get_auth_principal_api_key_path(monkeypatch):
    def _fake_get_settings() -> Any:
        return SimpleNamespace(PII_REDACT_LOGS=False)

    def _fake_is_single_user_mode() -> bool:
        return False

    async def _fake_get_request_user(request, token: str = "", api_key: str | None = None) -> User:
        request.state.user_id = 7
        request.state.api_key_id = 100
        request.state.org_ids = [1, 2]
        request.state.team_ids = [3]
        return User(
            id=7,
            username="api-user",
            is_active=True,
            roles=["user"],
            permissions=["media.read"],
            is_admin=False,
        )

    monkeypatch.setattr(
        "tldw_Server_API.app.core.AuthNZ.auth_principal_resolver.get_settings",
        _fake_get_settings,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.AuthNZ.auth_principal_resolver.is_single_user_mode",
        _fake_is_single_user_mode,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.AuthNZ.auth_principal_resolver.get_request_user",
        _fake_get_request_user,
    )

    req = _make_request(headers={"X-API-KEY": "vk-key"})

    principal = await get_auth_principal(req)
    assert principal.kind == "api_key"
    assert principal.user_id == 7
    assert principal.api_key_id == 100
    assert principal.org_ids == [1, 2]
    assert principal.team_ids == [3]


@pytest.mark.asyncio
async def test_get_auth_principal_missing_credentials_raises_401(monkeypatch):
    def _fake_get_settings() -> Any:
        return SimpleNamespace(PII_REDACT_LOGS=False)

    def _fake_is_single_user_mode() -> bool:
        return False

    monkeypatch.setattr(
        "tldw_Server_API.app.core.AuthNZ.auth_principal_resolver.get_settings",
        _fake_get_settings,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.AuthNZ.auth_principal_resolver.is_single_user_mode",
        _fake_is_single_user_mode,
    )

    req = _make_request()

    with pytest.raises(HTTPException) as exc_info:
        await get_auth_principal(req)

    assert exc_info.value.status_code == 401

