from types import SimpleNamespace

import pytest
from fastapi import HTTPException, status
from starlette.requests import Request

from tldw_Server_API.app.core.AuthNZ import User_DB_Handling as user_handling
from tldw_Server_API.app.core.AuthNZ.settings import reset_settings


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
    # Configure a synthetic single-user id for this test.
    fake_settings = SimpleNamespace(SINGLE_USER_FIXED_ID=99, PII_REDACT_LOGS=False)

    monkeypatch.setattr(user_handling, "get_settings", lambda: fake_settings)

    async def _fake_authenticate_api_key_user(request, api_key: str) -> user_handling.User:
        # The verification helper should pass the raw API key through.
        assert api_key == "test-api-key-abcdefghijklmnopqrstuvwxyz"
        return user_handling.User(id=fake_settings.SINGLE_USER_FIXED_ID, username="single_user", is_active=True)

    monkeypatch.setattr(user_handling, "authenticate_api_key_user", _fake_authenticate_api_key_user)

    request = _build_request()

    # Happy path: Authorization bearer with the configured key resolves to the single-user id.
    assert await user_handling.verify_single_user_api_key(
        request,
        api_key=None,
        authorization="Bearer test-api-key-abcdefghijklmnopqrstuvwxyz",
    ) is True

    # Missing credentials should raise 401.
    with pytest.raises(HTTPException):
        await user_handling.verify_single_user_api_key(request, api_key=None, authorization=None)


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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "auth_mode,expected_subject",
    [
        ("multi_user", None),
        ("single_user", "single_user"),
    ],
)
async def test_api_key_principal_subject_single_user_only_in_single_user_mode(
    monkeypatch,
    auth_mode: str,
    expected_subject: str | None,
):
    monkeypatch.setenv("AUTH_MODE", auth_mode)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("SINGLE_USER_FIXED_ID", "77")
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
            "is_superuser": True,
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
    await user_handling.get_request_user(request, api_key="valid-key", token=None)
    ctx = getattr(request.state, "auth", None)
    assert ctx is not None
    assert getattr(ctx.principal, "subject", None) == expected_subject

    for env_key in ("AUTH_MODE", "DATABASE_URL", "SINGLE_USER_FIXED_ID"):
        monkeypatch.delenv(env_key, raising=False)
    reset_settings()
