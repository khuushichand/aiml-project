from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response
from starlette.requests import Request
from starlette.types import Scope

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import (
    get_current_user,
    get_current_active_user,
)
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User


def _make_request(headers: dict[str, str] | None = None, path: str = "/") -> Request:
    scope: Scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": [(k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in (headers or {}).items()],
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_get_current_user_missing_credentials_returns_401(monkeypatch):
    # Ensure we are not in single-user mode for this invariant
    # Dummy session manager and db pool (unreachable in this path)
    fake_session = SimpleNamespace(is_token_blacklisted=lambda *_args, **_kwargs: False)
    fake_db_pool = SimpleNamespace(pool=None)

    request = _make_request()
    response = Response()

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(
            request=request,
            response=response,
            credentials=None,
            session_manager=fake_session,
            db_pool=fake_db_pool,
            x_api_key=None,
        )

    exc = exc_info.value
    assert exc.status_code == 401
    assert exc.headers.get("WWW-Authenticate") == "Bearer"
    assert "Authentication required" in str(exc.detail)


@pytest.mark.asyncio
async def test_get_request_user_multi_user_missing_credentials_returns_401(monkeypatch):
    from tldw_Server_API.app.core.AuthNZ import User_DB_Handling as udh

    fake_settings = SimpleNamespace(
        AUTH_MODE="multi_user",
        PII_REDACT_LOGS=False,
    )

    monkeypatch.setattr(udh, "get_settings", lambda: fake_settings)

    request = _make_request()

    with pytest.raises(HTTPException) as exc_info:
        await get_request_user(
            request=request,
            api_key=None,
            token=None,
            legacy_token_header=None,
        )

    exc = exc_info.value
    assert exc.status_code == 401
    assert "Not authenticated (provide Bearer token or X-API-KEY)" in str(exc.detail)
    assert exc.headers.get("WWW-Authenticate") == "Bearer"


@pytest.mark.asyncio
async def test_get_request_user_single_user_valid_api_key_sets_user_id(monkeypatch):
    from tldw_Server_API.app.core.AuthNZ import User_DB_Handling as udh

    fake_user = User(id=99, username="single_user", is_active=True)

    async def _fake_authenticate_api_key_user(request, api_key: str) -> User:
        assert api_key == "test-api-key"
        request.state.user_id = fake_user.id
        request.state.org_ids = []
        request.state.team_ids = []
        return fake_user

    monkeypatch.setattr(udh, "authenticate_api_key_user", _fake_authenticate_api_key_user)

    request = _make_request(headers={"X-API-KEY": "test-api-key"})

    user = await get_request_user(
        request=request,
        api_key="test-api-key",
        token=None,
        legacy_token_header=None,
    )

    assert int(user.id) == fake_user.id
    assert getattr(request.state, "user_id", None) == fake_user.id


@pytest.mark.asyncio
async def test_get_current_active_user_passes_through_for_active_verified_user():
    active_user = {
        "id": 1,
        "username": "active-user",
        "is_active": True,
        "is_verified": True,
        "roles": ["user"],
        "permissions": ["media.read"],
    }

    result = await get_current_active_user(current_user=active_user)

    # get_current_active_user should be a thin wrapper over get_current_user
    # for active, verified users and return the same dict unchanged.
    assert result is active_user
    assert result["id"] == active_user["id"]
    assert result["roles"] == active_user["roles"]
    assert result["permissions"] == active_user["permissions"]


@pytest.mark.asyncio
async def test_get_current_active_user_inactive_user_raises_403():
    inactive_user = {
        "id": 1,
        "username": "inactive-user",
        "is_active": False,
        "is_verified": True,
    }

    with pytest.raises(HTTPException) as exc_info:
        await get_current_active_user(current_user=inactive_user)

    exc = exc_info.value
    assert exc.status_code == 403
    assert "inactive" in str(exc.detail)


@pytest.mark.asyncio
async def test_get_current_active_user_unverified_user_raises_403():
    unverified_user = {
        "id": 1,
        "username": "unverified-user",
        "is_active": True,
        "is_verified": False,
    }

    with pytest.raises(HTTPException) as exc_info:
        await get_current_active_user(current_user=unverified_user)

    exc = exc_info.value
    assert exc.status_code == 403
    assert "Email verification required" in str(exc.detail)
