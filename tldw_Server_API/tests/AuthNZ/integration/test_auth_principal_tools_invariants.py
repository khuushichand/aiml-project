import pytest
from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal, AuthContext


pytestmark = pytest.mark.integration


def _install_auth_capture(app: FastAPI):
    """
    Install a lightweight wrapper around get_auth_principal that records
    principal/state alignment for the last request.
    """
    captured = {}
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


def _restore_auth_capture(app: FastAPI, original_get_auth_principal):
    try:
        app.dependency_overrides.pop(auth_deps.get_auth_principal, None)
    finally:
        auth_deps.get_auth_principal = original_get_auth_principal  # type: ignore[assignment]


def test_tools_execute_api_key_principal_and_state_alignment(isolated_test_environment, monkeypatch):
    """
    Multi-user API-key happy path for a representative tools route:

    - Register a user and create a real API key.
    - Grant tools.execute:* permission.
    - Call /api/v1/tools/execute and assert that request.state.* and
      request.state.auth.principal stay aligned with AuthPrincipal, including
      api_key_id.
    """
    client, db_name = isolated_test_environment
    assert isinstance(client, TestClient)

    from tldw_Server_API.app.core.AuthNZ.settings import get_settings

    settings = get_settings()
    assert settings.AUTH_MODE == "multi_user"

    # 1. Register a user via the real auth endpoint.
    username = "tools_invariants_user"
    password = "Str0ngP@ssw0rd!"
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": "tools_invariants_user@example.com",
            "password": password,
        },
    )
    assert reg.status_code == 200, reg.text

    # 2. Create an API key for this user and grant tools.execute:*.
    from tldw_Server_API.tests.AuthNZ.integration.test_auth_principal_media_rag_invariants import (  # type: ignore  # noqa: E501
        _create_api_key,
        _run_async,
    )

    api_key_info = _run_async(_create_api_key(db_name, username))
    api_key = api_key_info["key"]

    # Ensure tools.execute:* is present via RBAC helper override so the route
    # passes require_permissions("tools.execute:*") regardless of backend.
    from tldw_Server_API.app.core.AuthNZ import User_DB_Handling as user_db_handling

    _orig_get_effective_permissions = user_db_handling.get_effective_permissions

    def _patched_get_effective_permissions(user_id: int):
        perms = _orig_get_effective_permissions(user_id)
        if "tools.execute:*" not in perms:
            perms = list(perms) + ["tools.execute:*"]
        return perms

    monkeypatch.setattr(user_db_handling, "get_effective_permissions", _patched_get_effective_permissions)

    # 3. Install auth capture and call /api/v1/tools/execute.
    from tldw_Server_API.app.main import app as fastapi_app

    app = fastapi_app
    captured, original = _install_auth_capture(app)
    try:
        # Minimal valid execute body; executor behavior is not under test here.
        resp = client.post(
            "/api/v1/tools/execute",
            headers={"X-API-KEY": api_key},
            json={"tool_name": "echo", "arguments": {}, "dry_run": True, "idempotency_key": None},
        )
        # We only require that auth succeeded. A 403 may still occur at the
        # tool layer if the named tool is unavailable; distinguish from auth
        # failures by allowing 403 with the current tool-level message.
        assert resp.status_code != 401, resp.text
        if resp.status_code == 403:
            assert "Permission denied for tool or tool not found" in resp.text

        principal = captured.get("principal")
        state = captured.get("state")
        state_auth_principal = captured.get("state_auth_principal")

        assert principal is not None
        assert state is not None
        assert state_auth_principal is not None

        # AuthPrincipal reflects API-key based identity.
        assert principal["kind"] == "api_key"
        assert principal["user_id"] is not None
        assert principal["api_key_id"] is not None

        # request.state mirrors principal identity (user_id and api_key_id).
        assert str(state["user_id"]) == str(principal["user_id"])
        assert state["api_key_id"] is not None
        assert str(state["api_key_id"]) == str(principal["api_key_id"])

        # request.state.auth.principal mirrors both principal and state.
        assert state_auth_principal["kind"] == principal["kind"]
        assert str(state_auth_principal["user_id"]) == str(principal["user_id"])
        assert str(state_auth_principal["api_key_id"]) == str(principal["api_key_id"])
        assert str(state_auth_principal["api_key_id"]) == str(state["api_key_id"])
    finally:
        _restore_auth_capture(app, original)
