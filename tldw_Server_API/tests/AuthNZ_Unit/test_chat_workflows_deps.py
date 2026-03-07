from typing import Any

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps import chat_workflows_deps as deps
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User


def _make_app() -> FastAPI:
    app = FastAPI()

    @app.get("/cw/me")
    async def me(ctx: dict[str, Any] = Depends(deps.get_chat_workflows_user)):
        return ctx

    return app


def test_chat_workflows_user_claims_permissions(monkeypatch):
    calls: dict[str, Any] = {}

    async def fake_get_request_user(request, api_key=None, token=None, legacy_token_header=None):
        calls["api_key"] = api_key
        calls["token"] = token
        return User(
            id=7,
            username="workflow-user",
            roles=["user"],
            permissions=["chat_workflows.run", "chat_workflows.write"],
            is_admin=False,
        )

    monkeypatch.setattr(deps, "get_request_user", fake_get_request_user, raising=True)

    app = _make_app()
    client = TestClient(app)
    response = client.get("/cw/me", headers={"Authorization": "Bearer token"})

    assert response.status_code == 200
    assert "chat_workflows.run" in response.json()["permissions"]
    assert response.json()["client_id"] == "web"
    assert calls["api_key"] is None
    assert calls["token"] == "token"


def test_chat_workflows_user_requires_auth_headers(monkeypatch):
    async def fake_get_request_user(*_args, **_kwargs):
        raise RuntimeError("should_not_be_called")

    monkeypatch.setattr(deps, "get_request_user", fake_get_request_user, raising=True)

    app = _make_app()
    client = TestClient(app)
    response = client.get("/cw/me")

    assert response.status_code == 401
