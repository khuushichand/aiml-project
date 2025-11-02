import os
from typing import Any, Dict

import pytest
from fastapi import FastAPI, Depends
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


@pytest.mark.parametrize(
    "headers,expected_api_key,expected_token,expected_user",
    [
        ( {"X-API-KEY": "abc123"}, "abc123", None, "u-key" ),
        ( {"Authorization": "Bearer tok-xyz"}, None, "tok-xyz", "u-bearer" ),
        ( {"X-API-KEY": "abc123", "Authorization": "Bearer tok-xyz"}, "abc123", "tok-xyz", "u-bearer" ),
    ],
)
def test_get_prompt_studio_user_header_forwarding(monkeypatch, headers, expected_api_key, expected_token, expected_user):
    calls: Dict[str, Any] = {}

    async def fake_get_request_user(request, api_key=None, token=None, legacy_token_header=None):
        calls["api_key"] = api_key
        calls["token"] = token
        # Simulate auth precedence: prefer bearer token when present
        uid = "u-bearer" if token else "u-key"
        return User(id=uid, username=uid, is_active=True)

    monkeypatch.setattr(deps, "get_request_user", fake_get_request_user, raising=True)

    app = _make_app()
    client = TestClient(app)
    r = client.get("/ps/me", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()

    # Header extraction forwarded correctly
    assert calls.get("api_key") == expected_api_key
    assert calls.get("token") == expected_token
    # Resulting user context reflects fake identity (Bearer preferred when present)
    assert data.get("user_id") == expected_user
