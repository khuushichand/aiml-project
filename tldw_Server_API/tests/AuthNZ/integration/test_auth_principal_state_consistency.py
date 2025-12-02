import os
from types import SimpleNamespace
from typing import Dict, Any

import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import (
    get_auth_principal,
    get_current_user,
)
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal


pytestmark = pytest.mark.integration


router = APIRouter()


@router.get("/whoami/current_user")
async def whoami_current_user(
    user: Dict[str, Any] = Depends(get_current_user),
):
    return {
        "id": user.get("id"),
        "roles": user.get("roles"),
        "permissions": user.get("permissions"),
    }


@router.get("/whoami/principal")
async def whoami_principal(
    principal: AuthPrincipal = Depends(get_auth_principal),
):
    return {
        "principal_id": principal.principal_id,
        "kind": principal.kind,
        "user_id": principal.user_id,
        "api_key_id": principal.api_key_id,
        "roles": principal.roles,
        "permissions": principal.permissions,
        "org_ids": principal.org_ids,
        "team_ids": principal.team_ids,
    }


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return app


@pytest.fixture
def single_user_app(monkeypatch) -> TestClient:
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("SINGLE_USER_API_KEY", "test-api-key-12345")
    # Ensure tests see the single-user settings
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings

    reset_settings()
    app = _make_app()
    return TestClient(app)


def test_single_user_flow_principal_matches_state(single_user_app: TestClient):
    resp = single_user_app.get(
        "/api/v1/whoami/current_user",
        headers={"X-API-KEY": os.getenv("SINGLE_USER_API_KEY", "test-api-key-12345")},
    )
    assert resp.status_code == 200
    user = resp.json()

    resp_principal = single_user_app.get(
        "/api/v1/whoami/principal",
        headers={"X-API-KEY": os.getenv("SINGLE_USER_API_KEY", "test-api-key-12345")},
    )
    assert resp_principal.status_code == 200
    principal = resp_principal.json()

    assert principal["kind"] == "single_user"
    assert int(principal["user_id"]) == int(user["id"])
    assert principal["roles"]
    assert principal["permissions"]


@pytest.mark.asyncio
async def test_multi_user_jwt_and_api_key_status_codes(monkeypatch):
    """
    Smoke-test that missing credentials still yield the expected 401 semantics
    when get_current_user and get_auth_principal coexist.
    """
    from tldw_Server_API.app.core.AuthNZ import User_DB_Handling as udh
    from tldw_Server_API.app.core.AuthNZ import auth_principal_resolver as apr

    # Force multi-user mode
    monkeypatch.setattr(udh, "is_single_user_mode", lambda: False)
    monkeypatch.setattr(apr, "is_single_user_mode", lambda: False)
    fake_settings = SimpleNamespace(
        AUTH_MODE="multi_user",
        PII_REDACT_LOGS=False,
    )
    monkeypatch.setattr(udh, "get_settings", lambda: fake_settings)

    app = _make_app()
    client = TestClient(app)

    # Missing credentials -> get_current_user should return 401 Authentication required
    resp = client.get("/api/v1/whoami/current_user")
    assert resp.status_code == 401
    assert "Authentication required" in resp.json()["detail"]
    assert resp.headers.get("WWW-Authenticate") == "Bearer"

    # Missing credentials -> get_auth_principal should return 401 Not authenticated...
    resp2 = client.get("/api/v1/whoami/principal")
    assert resp2.status_code == 401
    assert "Not authenticated (provide Bearer token or X-API-KEY)" in resp2.json()["detail"]
    assert resp2.headers.get("WWW-Authenticate") == "Bearer"
