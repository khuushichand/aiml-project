import os
from types import SimpleNamespace
from typing import Dict, Any

import pytest
from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import (
    get_auth_principal,
    get_current_user,
)
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


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


@router.get("/whoami/current_user_and_request_user")
async def whoami_current_user_and_request_user(
    request: Request,
    principal: AuthPrincipal = Depends(get_auth_principal),
    current_user: Dict[str, Any] = Depends(get_current_user),
    request_user: User = Depends(get_request_user),
):
    auth_ctx = getattr(request.state, "auth", None)
    if auth_ctx is not None:
        cp = auth_ctx.principal
        state_auth_principal: Dict[str, Any] | None = {
            "principal_id": getattr(cp, "principal_id", None),
            "kind": getattr(cp, "kind", None),
            "user_id": getattr(cp, "user_id", None),
            "api_key_id": getattr(cp, "api_key_id", None),
            "roles": getattr(cp, "roles", None),
            "permissions": getattr(cp, "permissions", None),
            "org_ids": getattr(cp, "org_ids", None),
            "team_ids": getattr(cp, "team_ids", None),
        }
    else:
        state_auth_principal = None

    return {
        "principal": {
            "principal_id": principal.principal_id,
            "kind": principal.kind,
            "user_id": principal.user_id,
            "api_key_id": principal.api_key_id,
            "roles": principal.roles,
            "permissions": principal.permissions,
            "org_ids": principal.org_ids,
            "team_ids": principal.team_ids,
        },
        "current_user": {
            "id": current_user.get("id"),
            "roles": current_user.get("roles"),
            "permissions": current_user.get("permissions"),
        },
        "request_user": {
            "id": getattr(request_user, "id", None),
            "roles": list(getattr(request_user, "roles", []) or []),
            "permissions": list(getattr(request_user, "permissions", []) or []),
            "is_admin": bool(getattr(request_user, "is_admin", False)),
        },
        "state": {
            "user_id": getattr(request.state, "user_id", None),
            "api_key_id": getattr(request.state, "api_key_id", None),
            "org_ids": getattr(request.state, "org_ids", None),
            "team_ids": getattr(request.state, "team_ids", None),
        },
        "state_auth_principal": state_auth_principal,
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

    assert principal["kind"] == "user"
    assert int(principal["user_id"]) == int(user["id"])
    assert principal["roles"]
    assert principal["permissions"]


def test_single_user_get_current_and_request_user_align_with_principal(
    single_user_app: TestClient,
):
    headers = {"X-API-KEY": os.getenv("SINGLE_USER_API_KEY", "test-api-key-12345")}

    resp = single_user_app.get("/api/v1/whoami/current_user_and_request_user", headers=headers)
    assert resp.status_code == 200
    payload = resp.json()

    principal = payload["principal"]
    current_user = payload["current_user"]
    request_user = payload["request_user"]
    state = payload["state"]
    state_auth_principal = payload["state_auth_principal"]

    # Principal identity should align with both user representations
    assert principal["kind"] == "user"
    assert principal["user_id"] is not None
    assert str(principal["user_id"]) == str(current_user["id"])
    assert str(principal["user_id"]) == str(request_user["id"])

    # request.state mirrors principal identity
    assert str(state["user_id"]) == str(principal["user_id"])
    assert state["api_key_id"] is None

    # AuthContext principal mirrors both principal and state
    assert state_auth_principal is not None
    assert state_auth_principal["kind"] == principal["kind"]
    assert str(state_auth_principal["user_id"]) == str(principal["user_id"])
    assert state_auth_principal["api_key_id"] == principal["api_key_id"]
    assert state_auth_principal["org_ids"] == principal["org_ids"]
    assert state_auth_principal["team_ids"] == principal["team_ids"]

    # Claims across principal, get_current_user, and get_request_user remain aligned
    assert principal["roles"] == current_user["roles"] == request_user["roles"]
    assert principal["permissions"] == current_user["permissions"] == request_user["permissions"]


def test_single_user_bearer_api_key_accepted(single_user_app: TestClient):
    token = os.getenv("SINGLE_USER_API_KEY", "test-api-key-12345")
    headers = {"Authorization": f"Bearer {token}"}

    resp = single_user_app.get("/api/v1/whoami/current_user", headers=headers)
    assert resp.status_code == 200
    user = resp.json()
    assert user["id"] is not None

    resp_combo = single_user_app.get(
        "/api/v1/whoami/current_user_and_request_user",
        headers=headers,
    )
    assert resp_combo.status_code == 200
    payload = resp_combo.json()

    principal = payload["principal"]
    current_user = payload["current_user"]
    request_user = payload["request_user"]

    assert principal["kind"] == "user"
    assert str(principal["user_id"]) == str(current_user["id"])
    assert str(principal["user_id"]) == str(request_user["id"])
    assert principal["roles"] == current_user["roles"] == request_user["roles"]
    assert principal["permissions"] == current_user["permissions"] == request_user["permissions"]


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
