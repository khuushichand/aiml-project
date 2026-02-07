import pytest
from fastapi import HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials
from starlette.requests import Request

from tldw_Server_API.app.api.v1.API_Deps import auth_deps


def _build_request() -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [
            (b"authorization", b"Bearer header.payload.sig"),
            (b"x-api-key", b"valid-api-key"),
        ],
        "client": ("127.0.0.1", 0),
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_get_current_user_falls_back_to_api_key_when_jwt_invalid(monkeypatch):
    request = _build_request()
    response = Response()
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="header.payload.sig")

    async def _fake_verify(_request, _token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="bad token")

    async def _fake_api_key_auth(_request, api_key: str):
        assert api_key == "valid-api-key"
        return {"id": 99, "is_active": True, "is_verified": True}

    monkeypatch.setattr(auth_deps, "verify_jwt_and_fetch_user", _fake_verify)
    monkeypatch.setattr(auth_deps, "_authenticate_api_key_from_request", _fake_api_key_auth)

    user = await auth_deps.get_current_user(
        request=request,
        response=response,
        credentials=creds,
        x_api_key="valid-api-key",
    )

    assert user["id"] == 99


@pytest.mark.asyncio
async def test_authenticate_api_key_test_mode_blocked_in_production(monkeypatch):
    request = _build_request()
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("ALLOW_TEST_MODE_IN_PRODUCTION", raising=False)

    monkeypatch.setattr(
        auth_deps,
        "get_settings",
        lambda: type(
            "StubSettings",
            (),
            {
                "AUTH_MODE": "multi_user",
                "SINGLE_USER_API_KEY": "local-ci-test-key",
                "DATABASE_URL": "postgresql://stub",
                "SINGLE_USER_FIXED_ID": 1,
            },
        )(),
    )

    with pytest.raises(HTTPException) as exc:
        await auth_deps._authenticate_api_key_from_request(request, "local-ci-test-key")
    assert exc.value.status_code == 500
    assert exc.value.detail == "Server configuration error"


@pytest.mark.asyncio
async def test_authenticate_api_key_test_mode_allows_non_production(monkeypatch):
    request = _build_request()
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("ALLOW_TEST_MODE_IN_PRODUCTION", raising=False)

    monkeypatch.setattr(
        auth_deps,
        "get_settings",
        lambda: type(
            "StubSettings",
            (),
            {
                "AUTH_MODE": "multi_user",
                "SINGLE_USER_API_KEY": "local-ci-test-key",
                "DATABASE_URL": "postgresql://stub",
                "SINGLE_USER_FIXED_ID": 777,
            },
        )(),
    )

    user = await auth_deps._authenticate_api_key_from_request(request, "local-ci-test-key")
    assert user["id"] == 777
    assert user["username"] == "single_user"
