from typing import Any, Dict, Tuple

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

    Mirrors the helper used in media/RAG/tools invariant tests.
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


def test_evaluations_list_jwt_principal_and_state_alignment(isolated_test_environment, monkeypatch):
    """
    Multi-user JWT happy path for a representative Evaluations route:

    - Register and log in a user.
    - Grant evals.read permission.
    - Call /api/v1/evaluations/ (list) and assert that request.state.* and
      request.state.auth.principal stay aligned with AuthPrincipal.
    """
    client, db_name = isolated_test_environment
    assert isinstance(client, TestClient)
    _ = db_name  # included for parity with other invariant tests

    from tldw_Server_API.app.core.AuthNZ.settings import get_settings

    settings = get_settings()
    assert settings.AUTH_MODE == "multi_user"

    # 1. Register and log in via real auth endpoints.
    username = "evals_invariants_user"
    password = "Str0ngP@ssw0rd!"
    reg = client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": "evals_invariants_user@example.com", "password": password},
    )
    assert reg.status_code == 200, reg.text

    login = client.post("/api/v1/auth/login", data={"username": username, "password": password})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Grant evals.read permission so the list endpoint passes require_permissions.
    from tldw_Server_API.tests.AuthNZ.integration.test_auth_principal_media_rag_invariants import (  # type: ignore  # noqa: E501
        _grant_user_permission,
        _run_async,
    )

    _run_async(_grant_user_permission(db_name, username, "evals.read"))

    # 3. Install the auth capture wrapper and call /api/v1/evaluations/.
    from tldw_Server_API.app.main import app as fastapi_app

    app = fastapi_app
    captured, original = _install_auth_capture(app)
    try:
        resp = client.get("/api/v1/evaluations/", headers=headers)
        assert resp.status_code == 200, resp.text

        principal = captured.get("principal")
        state = captured.get("state")
        state_auth_principal = captured.get("state_auth_principal")

        assert principal is not None
        assert state is not None
        assert state_auth_principal is not None

        # AuthPrincipal kind/user identity.
        assert principal["kind"] == "user"
        assert principal["user_id"] is not None
        # Evaluations list is not API-key-based in this flow.
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


def test_evaluations_admin_cleanup_jwt_principal_and_state_alignment(
    isolated_test_environment, monkeypatch, tmp_path
):
    """
    Multi-user JWT happy path for an Evaluations admin endpoint:

    - Register and log in a user.
    - Call /api/v1/evaluations/admin/idempotency/cleanup with a valid JWT bearer.
    - Assert that request.state.* and request.state.auth.principal stay aligned
      with AuthPrincipal for this admin-style route.

    Admin heaviness is relaxed via EVALS_HEAVY_ADMIN_ONLY=0 so we do not have
    to mutate roles; the claim-first invariants still exercise the principal
    resolver and request.state wiring.
    """
    client, db_name = isolated_test_environment
    assert isinstance(client, TestClient)
    _ = db_name  # kept for parity with other invariant tests

    from tldw_Server_API.app.core.AuthNZ.settings import get_settings

    settings = get_settings()
    assert settings.AUTH_MODE == "multi_user"

    # Relax heavy-admin gating so require_admin becomes a no-op for this test.
    monkeypatch.setenv("EVALS_HEAVY_ADMIN_ONLY", "false")
    # Also enable TESTING so evaluations_auth uses the test-tier rate limits
    # and avoids hitting real per-user policies during invariants.
    monkeypatch.setenv("TESTING", "true")

    # 1. Register and log in via real auth endpoints.
    username = "evals_admin_invariants_user"
    password = "Str0ngP@ssw0rd!"
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": "evals_admin_invariants_user@example.com",
            "password": password,
        },
    )
    assert reg.status_code == 200, reg.text

    login = client.post("/api/v1/auth/login", data={"username": username, "password": password})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Provide a minimal, deterministic Evaluations DB environment so the
    #    admin cleanup endpoint can run without touching real user DB paths.
    from pathlib import Path
    from tldw_Server_API.app.core.DB_Management import db_path_utils as dp_mod
    from tldw_Server_API.app.core.DB_Management import Evaluations_DB as eval_db_mod

    db_file = tmp_path / "evals.db"
    db_file.parent.mkdir(parents=True, exist_ok=True)
    db_file.touch()

    def _fake_get_single_user_id() -> int:
        return 1

    def _fake_get_user_base_directory(_user_id: int) -> Path:
        return tmp_path

    def _fake_get_evaluations_db_path(_user_id: int) -> Path:
        return db_file

    monkeypatch.setattr(dp_mod.DatabasePaths, "get_single_user_id", staticmethod(_fake_get_single_user_id))
    monkeypatch.setattr(
        dp_mod.DatabasePaths, "get_user_base_directory", staticmethod(_fake_get_user_base_directory)
    )
    monkeypatch.setattr(
        dp_mod.DatabasePaths, "get_evaluations_db_path", staticmethod(_fake_get_evaluations_db_path)
    )

    class _FakeEvalDB:
        def __init__(self, path: str):
            self.path = path
            self.called_with_ttl: int | None = None

        def cleanup_idempotency_keys(self, ttl_hours: int) -> int:
            self.called_with_ttl = ttl_hours
            return 5

    monkeypatch.setattr(eval_db_mod, "EvaluationsDatabase", _FakeEvalDB)

    # 3. Install the auth capture wrapper and call /api/v1/evaluations/admin/idempotency/cleanup.
    from tldw_Server_API.app.main import app as fastapi_app

    app = fastapi_app
    captured, original = _install_auth_capture(app)
    try:
        resp = client.post("/api/v1/evaluations/admin/idempotency/cleanup", headers=headers)
        assert resp.status_code == 200, resp.text

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


def test_evaluations_admin_cleanup_api_key_principal_and_state_alignment(
    isolated_test_environment, monkeypatch, tmp_path
):
    """
    Multi-user API-key happy path for an Evaluations admin endpoint:

    - Register a user and create a real API key.
    - Call /api/v1/evaluations/admin/idempotency/cleanup with X-API-KEY.
    - Assert that request.state.* and request.state.auth.principal stay aligned
      with AuthPrincipal for this admin-style route, including api_key_id.

    The evaluations_auth.verify_api_key dependency is overridden to behave as a
    lightweight compatibility shim so that the claim-first principal resolver
    remains the source of truth for identity in this test.
    """
    client, db_name = isolated_test_environment
    assert isinstance(client, TestClient)

    from tldw_Server_API.app.core.AuthNZ.settings import get_settings

    settings = get_settings()
    assert settings.AUTH_MODE == "multi_user"

    # Relax heavy-admin gating so require_admin becomes a no-op; the admin
    # role/claim behavior is pinned elsewhere in permissions/claims tests.
    monkeypatch.setenv("EVALS_HEAVY_ADMIN_ONLY", "false")
    # Use TESTING tier for rate limits to avoid exercising real evals policies here.
    monkeypatch.setenv("TESTING", "true")

    # 1. Register a user via the real auth endpoint.
    username = "evals_admin_api_key_invariants_user"
    password = "Str0ngP@ssw0rd!"
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": "evals_admin_api_key_invariants_user@example.com",
            "password": password,
        },
    )
    assert reg.status_code == 200, reg.text

    # 2. Create an API key for this user.
    from tldw_Server_API.tests.AuthNZ.integration.test_auth_principal_media_rag_invariants import (  # type: ignore  # noqa: E501
        _create_api_key,
        _run_async,
    )

    api_key_info = _run_async(_create_api_key(db_name, username))
    api_key = api_key_info["key"]

    # 3. Provide a minimal, deterministic Evaluations DB environment so the
    #    admin cleanup endpoint can run without touching real user DB paths.
    from pathlib import Path
    from tldw_Server_API.app.core.DB_Management import db_path_utils as dp_mod
    from tldw_Server_API.app.core.DB_Management import Evaluations_DB as eval_db_mod

    db_file = tmp_path / "evals_api_key.db"
    db_file.parent.mkdir(parents=True, exist_ok=True)
    db_file.touch()

    def _fake_get_single_user_id() -> int:
        return 1

    def _fake_get_user_base_directory(_user_id: int) -> Path:
        return tmp_path

    def _fake_get_evaluations_db_path(_user_id: int) -> Path:
        return db_file

    monkeypatch.setattr(dp_mod.DatabasePaths, "get_single_user_id", staticmethod(_fake_get_single_user_id))
    monkeypatch.setattr(
        dp_mod.DatabasePaths, "get_user_base_directory", staticmethod(_fake_get_user_base_directory)
    )
    monkeypatch.setattr(
        dp_mod.DatabasePaths, "get_evaluations_db_path", staticmethod(_fake_get_evaluations_db_path)
    )

    class _FakeEvalDB:
        def __init__(self, path: str):
            self.path = path
            self.called_with_ttl: int | None = None

        def cleanup_idempotency_keys(self, ttl_hours: int) -> int:
            self.called_with_ttl = ttl_hours
            return 7

    monkeypatch.setattr(eval_db_mod, "EvaluationsDatabase", _FakeEvalDB)

    # 4. Install the auth capture wrapper and override evaluations_auth.verify_api_key
    #    so that the claim-first principal resolver drives identity while the
    #    legacy helper acts as a simple compatibility shim.
    from tldw_Server_API.app.main import app as fastapi_app
    from tldw_Server_API.app.api.v1.endpoints import evaluations_auth as eval_auth

    app = fastapi_app
    captured, original = _install_auth_capture(app)

    async def _fake_verify_api_key(*_args, **_kwargs) -> str:
        return "vk-test"

    app.dependency_overrides[eval_auth.verify_api_key] = _fake_verify_api_key

    try:
        resp = client.post(
            "/api/v1/evaluations/admin/idempotency/cleanup",
            headers={"X-API-KEY": api_key},
        )
        assert resp.status_code == 200, resp.text

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
        assert state_auth_principal["org_ids"] == principal["org_ids"]
        assert state_auth_principal["team_ids"] == principal["team_ids"]
        assert state["org_ids"] == principal["org_ids"]
        assert state["team_ids"] == principal["team_ids"]
    finally:
        app.dependency_overrides.pop(eval_auth.verify_api_key, None)
        _restore_auth_capture(app, original)
