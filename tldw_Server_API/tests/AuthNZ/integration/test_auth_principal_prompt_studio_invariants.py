from typing import Any, Dict, Tuple

import os
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal, AuthContext


pytestmark = pytest.mark.integration


def _install_auth_capture(app: FastAPI) -> Tuple[Dict[str, Any], Any]:
    """
    Install a lightweight wrapper around get_auth_principal that records
    principal/state alignment for the last request.
    """
    captured: Dict[str, Any] = {}
    original_get_auth_principal = auth_deps.get_auth_principal

    async def _capturing_get_auth_principal(request: Request) -> AuthPrincipal:  # type: ignore[override]
        principal = await original_get_auth_principal(request)

        captured["principal"] = {
            "principal_id": principal.principal_id,
            "kind": principal.kind,
            "user_id": principal.user_id,
            "api_key_id": principal.api_key_id,
            "roles": list(principal.roles),
            "permissions": list(principal.permissions),
            "org_ids": list(principal.org_ids),
            "team_ids": list(principal.team_ids),
        }
        captured["state"] = {
            "user_id": getattr(request.state, "user_id", None),
            "api_key_id": getattr(request.state, "api_key_id", None),
            "org_ids": getattr(request.state, "org_ids", None),
            "team_ids": getattr(request.state, "team_ids", None),
        }

        ctx = getattr(request.state, "auth", None)
        if isinstance(ctx, AuthContext):
            cp = ctx.principal
            captured["state_auth_principal"] = {
                "principal_id": cp.principal_id,
                "kind": cp.kind,
                "user_id": cp.user_id,
                "api_key_id": cp.api_key_id,
                "roles": list(cp.roles),
                "permissions": list(cp.permissions),
                "org_ids": list(cp.org_ids),
                "team_ids": list(cp.team_ids),
            }
        else:
            captured["state_auth_principal"] = None

        return principal

    app.dependency_overrides[auth_deps.get_auth_principal] = _capturing_get_auth_principal
    return captured, original_get_auth_principal


def _restore_auth_capture(app: FastAPI, original_get_auth_principal: Any) -> None:
    try:
        app.dependency_overrides.pop(auth_deps.get_auth_principal, None)
    finally:
        auth_deps.get_auth_principal = original_get_auth_principal  # type: ignore[assignment]


def test_prompt_studio_projects_jwt_principal_and_state_alignment(isolated_test_environment, monkeypatch):
    """
    Multi-user JWT happy path for a representative Prompt Studio domain route:

    - Register and log in a user.
    - Call /api/v1/prompt-studio/projects/ (trailing slash) and assert that
      request.state.* and request.state.auth.principal stay aligned with
      AuthPrincipal.
    """
    client, db_name = isolated_test_environment
    assert isinstance(client, TestClient)
    _ = db_name  # parity with other invariant tests

    from tldw_Server_API.app.core.AuthNZ.settings import get_settings

    settings = get_settings()
    assert settings.AUTH_MODE == "multi_user"

    # Ensure Prompt Studio deps exercise the unified request-user path, not TEST_MODE shortcuts.
    monkeypatch.setenv("TEST_MODE", "false")
    # Avoid anonymous bypasses in Prompt Studio deps during this test.
    monkeypatch.delenv("ALLOW_ANONYMOUS_PROMPT_STUDIO", raising=False)

    # 1. Register and log in via real auth endpoints.
    username = "ps_invariants_user"
    password = "Str0ngP@ssw0rd!"
    reg = client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": "ps_invariants_user@example.com", "password": password},
    )
    assert reg.status_code == 200, reg.text

    login = client.post("/api/v1/auth/login", data={"username": username, "password": password})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Install the auth capture wrapper and call /api/v1/prompt-studio/projects/.
    from tldw_Server_API.app.main import app as fastapi_app

    app = fastapi_app
    captured, original = _install_auth_capture(app)
    try:
        # Use trailing slash path so get_prompt_studio_user treats it as authenticated.
        resp = client.get("/api/v1/prompt-studio/projects/", headers=headers)
        # Endpoint should succeed or return a well-formed 200 with empty list; focus on auth invariants.
        assert resp.status_code in (200, 404), resp.text

        principal = captured.get("principal")
        state = captured.get("state")
        state_auth_principal = captured.get("state_auth_principal")

        assert principal is not None
        assert state is not None
        assert state_auth_principal is not None

        # AuthPrincipal kind/user identity.
        assert principal["kind"] == "user"
        assert principal["user_id"] is not None
        assert principal["api_key_id"] is None

        # request.state mirrors principal identity (user_id, no api_key_id).
        assert str(state["user_id"]) == str(principal["user_id"])
        assert state["api_key_id"] is None

        # request.state.auth.principal mirrors principal and state.
        assert state_auth_principal["kind"] == principal["kind"]
        assert str(state_auth_principal["user_id"]) == str(principal["user_id"])
        assert state_auth_principal["api_key_id"] == principal["api_key_id"]
        assert state_auth_principal["org_ids"] == principal["org_ids"]
        assert state_auth_principal["team_ids"] == principal["team_ids"]
        assert state["org_ids"] == principal["org_ids"]
        assert state["team_ids"] == principal["team_ids"]
    finally:
        _restore_auth_capture(app, original)
