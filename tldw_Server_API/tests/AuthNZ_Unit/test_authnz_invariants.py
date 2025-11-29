from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response
from starlette.requests import Request
from starlette.types import Scope

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_current_user
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user


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
    from tldw_Server_API.app.api.v1.API_Deps import auth_deps as deps

    monkeypatch.setattr(deps, "is_single_user_mode", lambda: False)

    # Dummy session manager and db pool (unreachable in this path)
    fake_session = SimpleNamespace(is_token_blacklisted=lambda *args, **kwargs: False)
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

    # Force multi-user mode
    monkeypatch.setattr(udh, "is_single_user_mode", lambda: False)

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

    # Force single-user mode
    monkeypatch.setattr(udh, "is_single_user_mode", lambda: True)

    fake_settings = SimpleNamespace(
        AUTH_MODE="single_user",
        SINGLE_USER_API_KEY="test-api-key",
        SINGLE_USER_FIXED_ID=99,
        PII_REDACT_LOGS=False,
    )
    monkeypatch.setattr(udh, "get_settings", lambda: fake_settings)

    # Ensure app_settings fallback (if used) matches the same key
    monkeypatch.setattr(
        udh,
        "app_settings",
        {"SINGLE_USER_API_KEY": "test-api-key"},
        raising=False,
    )

    request = _make_request(headers={"X-API-KEY": "test-api-key"})

    user = await get_request_user(
        request=request,
        api_key="test-api-key",
        token=None,
        legacy_token_header=None,
    )

    assert int(user.id) == fake_settings.SINGLE_USER_FIXED_ID
    assert getattr(request.state, "user_id", None) == fake_settings.SINGLE_USER_FIXED_ID

