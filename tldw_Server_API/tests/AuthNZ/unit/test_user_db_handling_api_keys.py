import pytest
from fastapi import HTTPException, status
from starlette.requests import Request

from tldw_Server_API.app.core.AuthNZ import User_DB_Handling as user_handling
from tldw_Server_API.app.core.AuthNZ.settings import get_settings, reset_settings


def _build_request() -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [],
        "client": ("127.0.0.1", 0),
    }
    request = Request(scope)
    return request


@pytest.mark.asyncio
async def test_verify_single_user_api_key_accepts_bearer(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("SINGLE_USER_API_KEY", "test-api-key-abcdefghijklmnopqrstuvwxyz")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    reset_settings()

    request = _build_request()
    settings = get_settings()
    assert await user_handling.verify_single_user_api_key(
        request,
        api_key=None,
        authorization=f"Bearer {settings.SINGLE_USER_API_KEY}",
    ) is True

    with pytest.raises(HTTPException):
        await user_handling.verify_single_user_api_key(request, api_key=None, authorization=None)

    for env_key in ("AUTH_MODE", "SINGLE_USER_API_KEY", "DATABASE_URL"):
        monkeypatch.delenv(env_key, raising=False)
    reset_settings()


@pytest.mark.asyncio
async def test_get_request_user_rejects_inactive_api_key_user(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    reset_settings()

    class StubAPIKeyManager:
        async def validate_api_key(self, api_key: str, ip_address=None):
            return {"id": 1, "user_id": 42}

    async def fake_get_api_key_manager():
        return StubAPIKeyManager()

    async def fake_get_user_by_id(user_id: int):
        return {
            "id": user_id,
            "username": "inactive-user",
            "email": "inactive@example.com",
            "is_active": 0,
            "roles": [],
            "permissions": [],
        }

    async def fake_list_memberships(user_id: int):
        return []

    # Patch dependencies
    monkeypatch.setattr(user_handling, "get_api_key_manager", fake_get_api_key_manager)
    monkeypatch.setattr(
        "tldw_Server_API.app.core.DB_Management.Users_DB.get_user_by_id",
        fake_get_user_by_id,
    )
    monkeypatch.setattr(user_handling, "list_memberships_for_user", fake_list_memberships)
    monkeypatch.setattr(user_handling, "set_scope", lambda *_, **__: None)

    request = _build_request()

    with pytest.raises(HTTPException) as exc:
        await user_handling.get_request_user(request, api_key="test-api-key", token=None)

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
    assert exc.value.detail == "Inactive user"

    for env_key in ("AUTH_MODE", "DATABASE_URL"):
        monkeypatch.delenv(env_key, raising=False)
    reset_settings()


@pytest.mark.asyncio
async def test_get_request_user_allows_active_api_key_user(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    reset_settings()

    class StubAPIKeyManager:
        async def validate_api_key(self, api_key: str, ip_address=None):
            return {"id": 5, "user_id": 77}

    async def fake_get_api_key_manager():
        return StubAPIKeyManager()

    async def fake_get_user_by_id(user_id: int):
        return {
            "id": user_id,
            "username": "active-user",
            "email": "active@example.com",
            "is_active": 1,
            "is_superuser": False,
            "roles": [],
            "permissions": [],
        }

    async def fake_list_memberships(user_id: int):
        return []

    monkeypatch.setattr(user_handling, "get_api_key_manager", fake_get_api_key_manager)
    monkeypatch.setattr(
        "tldw_Server_API.app.core.DB_Management.Users_DB.get_user_by_id",
        fake_get_user_by_id,
    )
    monkeypatch.setattr(user_handling, "list_memberships_for_user", fake_list_memberships)
    monkeypatch.setattr(user_handling, "set_scope", lambda *_, **__: None)

    request = _build_request()
    user = await user_handling.get_request_user(request, api_key="valid-key", token=None)
    assert user.id == 77
    assert user.is_active is True

    for env_key in ("AUTH_MODE", "DATABASE_URL"):
        monkeypatch.delenv(env_key, raising=False)
    reset_settings()
