import pytest
from fastapi import HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials
from starlette.requests import Request

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.core.AuthNZ import auth_principal_resolver
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user
from tldw_Server_API.app.core.AuthNZ.jwt_service import JWTService, reset_jwt_service
from tldw_Server_API.app.core.AuthNZ.settings import reset_settings


def _build_request(headers: dict[str, str], client_host: str = "127.0.0.1") -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [
            (k.lower().encode("ascii"), v.encode("ascii")) for k, v in headers.items()
        ],
        "client": (client_host, 0),
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_get_auth_principal_accepts_service_token(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-service-secret-1234567890-abcdef")
    reset_settings()
    reset_jwt_service()

    jwt_service = JWTService()
    token = jwt_service.create_service_account_token(
        service_name="worker",
        permissions=["tools.execute:foo", "admin"],
    )
    request = _build_request({"Authorization": f"Bearer {token}"})

    principal = await auth_principal_resolver.get_auth_principal(request)

    assert principal.kind == "service"
    assert principal.subject == "service:worker"
    assert "tools.execute:foo" in principal.permissions
    assert principal.is_admin is True
    reset_settings()
    reset_jwt_service()


@pytest.mark.asyncio
async def test_get_auth_principal_rejects_service_token_from_nonlocal(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-service-secret-1234567890-abcdef")
    reset_settings()
    reset_jwt_service()

    jwt_service = JWTService()
    token = jwt_service.create_service_account_token(
        service_name="worker",
        permissions=["tools.execute:foo"],
    )
    request = _build_request(
        {"Authorization": f"Bearer {token}"},
        client_host="203.0.113.10",
    )

    with pytest.raises(HTTPException) as exc:
        await auth_principal_resolver.get_auth_principal(request)

    assert exc.value.status_code == 403
    reset_settings()
    reset_jwt_service()


@pytest.mark.asyncio
async def test_get_current_user_accepts_bearer_api_key_single_user(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("SINGLE_USER_API_KEY", "tldw_test_key_123456")
    monkeypatch.setenv("SINGLE_USER_FIXED_ID", "1")
    reset_settings()

    token = "tldw_test_key_123456"
    request = _build_request({"Authorization": f"Bearer {token}"})
    response = Response()
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    user = await auth_deps.get_current_user(
        request=request,
        response=response,
        credentials=creds,
        x_api_key=None,
    )

    assert user["id"] == 1
    assert "admin" in (user.get("roles") or [])
    reset_settings()


@pytest.mark.asyncio
async def test_get_auth_principal_accepts_bearer_api_key_single_user(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("SINGLE_USER_API_KEY", "tldw_test_key_123456")
    monkeypatch.setenv("SINGLE_USER_FIXED_ID", "1")
    reset_settings()

    token = "tldw_test_key_123456"
    request = _build_request({"Authorization": f"Bearer {token}"})

    principal = await auth_principal_resolver.get_auth_principal(request)

    assert principal.kind == "user"
    assert principal.subject == "single_user"
    assert principal.user_id == 1
    reset_settings()


@pytest.mark.asyncio
async def test_get_request_user_accepts_bearer_api_key_single_user(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("SINGLE_USER_API_KEY", "tldw_test_key_123456")
    monkeypatch.setenv("SINGLE_USER_FIXED_ID", "1")
    reset_settings()

    token = "tldw_test_key_123456"
    request = _build_request({"Authorization": f"Bearer {token}"})

    user = await get_request_user(request, token=token)

    assert getattr(user, "id_int", None) == 1
    reset_settings()


@pytest.mark.asyncio
async def test_single_user_legacy_bearer_token_rejected(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("SINGLE_USER_API_KEY", "tldw_test_key_123456")
    monkeypatch.setenv("SINGLE_USER_FIXED_ID", "1")
    reset_settings()

    token = "single-user-token-1"
    request = _build_request({"Authorization": f"Bearer {token}"})
    response = Response()
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    with pytest.raises(HTTPException) as exc:
        await auth_deps.get_current_user(
            request=request,
            response=response,
            credentials=creds,
            x_api_key=None,
        )

    assert exc.value.status_code == 401

    with pytest.raises(HTTPException) as exc2:
        await auth_principal_resolver.get_auth_principal(request)
    assert exc2.value.status_code == 401

    with pytest.raises(HTTPException) as exc3:
        await get_request_user(request, token=token)
    assert exc3.value.status_code == 401
    reset_settings()


@pytest.mark.asyncio
async def test_get_auth_principal_rejects_legacy_token_header(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    reset_settings()

    request = _build_request({"Token": "Bearer legacy-key"})

    with pytest.raises(HTTPException) as exc:
        await auth_principal_resolver.get_auth_principal(request)

    assert exc.value.status_code == 401
    reset_settings()
