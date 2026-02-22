from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_db_transaction
from tldw_Server_API.app.main import app


def _active_user_context() -> dict[str, object]:
    return {
        "id": 1,
        "username": "legacy-user",
        "email": "legacy@example.invalid",
        "role": "user",
        "is_active": True,
        "is_verified": True,
        "storage_quota_mb": 5120,
        "storage_used_mb": 0.0,
        "created_at": datetime.utcnow(),
        "last_login": None,
    }


def test_users_me_update_returns_404_when_update_affects_no_rows(auth_headers, monkeypatch) -> None:
    from tldw_Server_API.app.api.v1.endpoints import users as users_endpoints

    class _FakeCursor:
        rowcount = 0

    class _FakeDB:
        async def execute(self, *_args, **_kwargs):
            return _FakeCursor()

    async def _fake_get_db_transaction():
        yield _FakeDB()

    async def _fake_resolve_user_context(_principal, *, allow_missing: bool = False):
        del allow_missing
        return _active_user_context()

    monkeypatch.setattr(users_endpoints, "_resolve_user_context", _fake_resolve_user_context)
    app.dependency_overrides[get_db_transaction] = _fake_get_db_transaction
    try:
        with TestClient(app) as client:
            resp = client.put(
                "/api/v1/users/me",
                headers=auth_headers,
                json={"email": "updated@example.com"},
            )
    finally:
        app.dependency_overrides.pop(get_db_transaction, None)

    assert resp.status_code == 404
    assert resp.json().get("detail") == "User not found"


def test_users_me_update_succeeds_when_row_is_updated(auth_headers, monkeypatch) -> None:
    from tldw_Server_API.app.api.v1.endpoints import users as users_endpoints

    class _FakeCursor:
        rowcount = 1

    class _FakeDB:
        async def execute(self, *_args, **_kwargs):
            return _FakeCursor()

    async def _fake_get_db_transaction():
        yield _FakeDB()

    async def _fake_resolve_user_context(_principal, *, allow_missing: bool = False):
        del allow_missing
        return _active_user_context()

    monkeypatch.setattr(users_endpoints, "_resolve_user_context", _fake_resolve_user_context)
    app.dependency_overrides[get_db_transaction] = _fake_get_db_transaction
    try:
        with TestClient(app) as client:
            resp = client.put(
                "/api/v1/users/me",
                headers=auth_headers,
                json={"email": "updated@example.com"},
            )
    finally:
        app.dependency_overrides.pop(get_db_transaction, None)

    assert resp.status_code == 200
    payload = resp.json()
    assert payload.get("warning") == "deprecated_endpoint"
    assert payload.get("successor") == "/api/v1/users/me/profile"
    assert payload.get("email") == "updated@example.com"
