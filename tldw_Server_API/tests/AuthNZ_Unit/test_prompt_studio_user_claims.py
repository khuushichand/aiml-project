from typing import Any, Dict

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps import prompt_studio_deps as deps
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User


def _make_app() -> FastAPI:


     app = FastAPI()

    @app.get("/ps/me")
    async def whoami(user_ctx: Dict[str, Any] = Depends(deps.get_prompt_studio_user)):
        return user_ctx

    return app


@pytest.fixture(autouse=True)
def _ensure_not_test_mode(monkeypatch):
     # Ensure get_prompt_studio_user exercises header-forwarding path
    monkeypatch.setenv("TEST_MODE", "false")
    yield


def test_prompt_studio_user_claims_admin_from_user_object(monkeypatch):


     calls: Dict[str, Any] = {}

    async def fake_get_request_user(request, api_key=None, token=None, legacy_token_header=None):
        calls["api_key"] = api_key
        calls["token"] = token
        return User(
            id=1,
            username="admin-user",
            is_active=True,
            roles=["admin"],
            permissions=["prompt_studio.admin"],
            is_admin=False,
        )

    monkeypatch.setattr(deps, "get_request_user", fake_get_request_user, raising=True)

    app = _make_app()
    client = TestClient(app)
    r = client.get("/ps/me", headers={"Authorization": "Bearer tok-admin"})
    assert r.status_code == 200, r.text
    data = r.json()

    # Claims forwarded correctly
    assert calls.get("token") == "tok-admin"
    assert data.get("user_id") == "1"
    # Admin derived from roles/claims, not AUTH_MODE
    assert data.get("is_admin") is True
    assert "prompt_studio.admin" in data.get("permissions", [])


def test_prompt_studio_user_claims_non_admin(monkeypatch):


     async def fake_get_request_user(request, api_key=None, token=None, legacy_token_header=None):
        return User(
            id=2,
            username="regular-user",
            is_active=True,
            roles=["user"],
            permissions=["prompt_studio.read"],
            is_admin=False,
        )

    monkeypatch.setattr(deps, "get_request_user", fake_get_request_user, raising=True)

    app = _make_app()
    client = TestClient(app)
    r = client.get("/ps/me", headers={"Authorization": "Bearer tok-user"})
    assert r.status_code == 200, r.text
    data = r.json()

    assert data.get("user_id") == "2"
    assert data.get("is_admin") is False
    assert data.get("permissions") == ["prompt_studio.read"]
