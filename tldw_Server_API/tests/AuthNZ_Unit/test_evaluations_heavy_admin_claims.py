import os
from types import SimpleNamespace
from typing import Optional

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthContext, AuthPrincipal


def _make_principal(
    *,
    roles: Optional[list[str]] = None,
    permissions: Optional[list[str]] = None,
    is_admin: bool = False,
) -> AuthPrincipal:
    return AuthPrincipal(
        kind="user",
        user_id=1,
        api_key_id=None,
        subject=None,
        token_type="access",
        jti=None,
        roles=list(roles or []),
        permissions=list(permissions or []),
        is_admin=is_admin,
        org_ids=[],
        team_ids=[],
    )


def _build_app_with_admin_cleanup(principal: AuthPrincipal) -> FastAPI:
    from tldw_Server_API.app.api.v1.endpoints import evaluations_unified as eval_unified
    from tldw_Server_API.app.core.AuthNZ import User_DB_Handling as udh
    from tldw_Server_API.app.api.v1.endpoints import evaluations_auth as eval_auth

    app = FastAPI()
    app.include_router(eval_unified.router, prefix="/api/v1")

    async def _fake_get_auth_principal(request: Request):
        ctx = AuthContext(
            principal=principal,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent") if request.headers else None,
            request_id=request.headers.get("X-Request-ID") if request.headers else None,
        )
        request.state.auth = ctx
        return principal

    app.dependency_overrides[auth_deps.get_auth_principal] = _fake_get_auth_principal

    async def _fake_verify_api_key() -> str:
        return "vk-test"

    app.dependency_overrides[eval_auth.verify_api_key] = _fake_verify_api_key

    async def _fake_get_request_user():
        return SimpleNamespace(
            id=principal.user_id,
            username="eval-user",
            is_active=True,
            roles=list(principal.roles),
            permissions=list(principal.permissions),
            is_admin=principal.is_admin,
        )

    app.dependency_overrides[udh.get_request_user] = _fake_get_request_user
    app.dependency_overrides[eval_auth.get_eval_request_user] = _fake_get_request_user

    # Use a small in-memory DB path for the cleanup helper
    from pathlib import Path
    from tldw_Server_API.app.core.DB_Management import db_path_utils as dp_mod
    from tldw_Server_API.app.core.DB_Management import Evaluations_DB as eval_db_mod

    tmp = Path(os.getenv("PYTEST_TMPDIR", "/tmp")) / "evals_admin_cleanup.db"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.touch(exist_ok=True)

    def _fake_get_single_user_id() -> int:

             return principal.user_id or 1

    def _fake_get_user_base_directory(_user_id: int) -> Path:
        return tmp.parent

    def _fake_get_evaluations_db_path(_user_id: int) -> Path:
        return tmp

    app.dependency_overrides[dp_mod.DatabasePaths.get_single_user_id] = lambda: _fake_get_single_user_id()  # type: ignore[assignment]
    app.dependency_overrides[dp_mod.DatabasePaths.get_user_base_directory] = lambda _uid: _fake_get_user_base_directory(_uid)  # type: ignore[assignment]
    app.dependency_overrides[dp_mod.DatabasePaths.get_evaluations_db_path] = lambda _uid: _fake_get_evaluations_db_path(_uid)  # type: ignore[assignment]

    class _FakeEvalDB:
        def __init__(self, path: str):
            self.path = path

        def cleanup_idempotency_keys(self, ttl_hours: int) -> int:
            return 1

    app.dependency_overrides[eval_db_mod.EvaluationsDatabase] = _FakeEvalDB  # type: ignore[assignment]

    return app


@pytest.mark.unit
def test_require_admin_helper_respects_env_guard(monkeypatch):
     from fastapi import HTTPException
    from tldw_Server_API.app.api.v1.endpoints.evaluations_auth import require_admin

    user = SimpleNamespace(is_admin=False, role="user", roles=["user"])
    monkeypatch.setenv("EVALS_HEAVY_ADMIN_ONLY", "true")
    with pytest.raises(HTTPException) as excinfo:
        require_admin(user)
    assert excinfo.value.status_code == 403

    # When guard disabled, helper should no-op even for non-admins.
    monkeypatch.setenv("EVALS_HEAVY_ADMIN_ONLY", "false")
    require_admin(user)


@pytest.mark.unit
def test_admin_cleanup_idempotency_forbidden_without_admin_role(monkeypatch):
     principal = _make_principal(roles=["user"], permissions=[], is_admin=False)
    app = _build_app_with_admin_cleanup(principal)
    monkeypatch.setenv("EVALS_HEAVY_ADMIN_ONLY", "true")

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/evaluations/admin/idempotency/cleanup",
            headers={"Authorization": "Bearer test"},
        )
    assert resp.status_code == 403


@pytest.mark.unit
def test_admin_cleanup_idempotency_allowed_for_admin(monkeypatch):
     principal = _make_principal(roles=["admin"], permissions=[], is_admin=True)
    app = _build_app_with_admin_cleanup(principal)
    monkeypatch.setenv("EVALS_HEAVY_ADMIN_ONLY", "true")

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/evaluations/admin/idempotency/cleanup",
            headers={"Authorization": "Bearer test"},
        )
    assert resp.status_code == 200
    body = resp.json()
    # In a fresh test environment there may be zero stale keys; the important
    # invariant is that an admin can call the endpoint successfully and that
    # the response includes a numeric deleted_total field.
    assert isinstance(body.get("deleted_total"), int)


@pytest.mark.unit
def test_admin_cleanup_idempotency_allows_roles_admin_without_is_admin(monkeypatch):
     """
    Ensure that a principal with roles=['admin'] but is_admin=False is still
    treated as admin by the heavy-evals gate.
    """
    principal = _make_principal(roles=["admin"], permissions=[], is_admin=False)
    app = _build_app_with_admin_cleanup(principal)
    monkeypatch.setenv("EVALS_HEAVY_ADMIN_ONLY", "true")

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/evaluations/admin/idempotency/cleanup",
            headers={"Authorization": "Bearer test"},
        )
    assert resp.status_code == 200
