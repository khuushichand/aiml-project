import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.types import Scope

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.api.v1.endpoints.evaluations_crud import (
    RBAC_EVALS_CREATE,
    crud_router,
)
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal, AuthContext


def _make_request(scope_overrides: Dict[str, Any] | None = None) -> Request:
    scope: Scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/evaluations/",
        "headers": [],
        "client": ("127.0.0.1", 12345),
    }
    if scope_overrides:
        scope.update(scope_overrides)
    return Request(scope)


def _build_app_with_overrides(principal: AuthPrincipal):
    from fastapi import FastAPI, Depends

    app = FastAPI()
    app.include_router(crud_router, prefix="/api/v1/evaluations")

    async def _fake_get_auth_principal(request: Request) -> AuthPrincipal:
        ip = request.client.host if request.client else None
        ua = request.headers.get("User-Agent") if request.headers else None
        request_id = request.headers.get("X-Request-ID") if request.headers else None
        ctx = AuthContext(
            principal=principal,
            ip=ip,
            user_agent=ua,
            request_id=request_id,
        )
        request.state.auth = ctx
        return principal

    app.dependency_overrides[auth_deps.get_auth_principal] = _fake_get_auth_principal

    async def _fake_verify_api_key() -> str:
        return "vk-test"

    from tldw_Server_API.app.api.v1.endpoints import evaluations_auth as eval_auth

    app.dependency_overrides[eval_auth.verify_api_key] = _fake_verify_api_key

    async def _fake_get_request_user() -> SimpleNamespace:
        return SimpleNamespace(
            id=1,
            username="eval-user",
            is_active=True,
            roles=list(principal.roles),
            permissions=list(principal.permissions),
            is_admin=principal.is_admin,
        )

    from tldw_Server_API.app.core.AuthNZ import User_DB_Handling as udh

    app.dependency_overrides[udh.get_request_user] = _fake_get_request_user

    async def _noop_rbac_rate_limit(*_args, **_kwargs) -> None:
        return None

    app.dependency_overrides[RBAC_EVALS_CREATE] = _noop_rbac_rate_limit

    return app


@pytest.mark.asyncio
async def test_evaluations_list_requires_auth_principal_and_api_key():
    app = _build_app_with_overrides(
        AuthPrincipal(
            kind="anonymous",
            user_id=None,
            api_key_id=None,
            subject=None,
            token_type=None,
            jti=None,
            roles=[],
            permissions=[],
            is_admin=False,
            org_ids=[],
            team_ids=[],
        )
    )

    with TestClient(app) as client:
        resp = client.get("/api/v1/evaluations/")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_evaluations_list_forbidden_without_claims():
    principal = AuthPrincipal(
        kind="user",
        user_id=1,
        api_key_id=None,
        subject=None,
        token_type="access",
        jti=None,
        roles=["user"],
        permissions=[],  # no evals.read
        is_admin=False,
        org_ids=[],
        team_ids=[],
    )
    app = _build_app_with_overrides(principal)

    with TestClient(app) as client:
        resp = client.get("/api/v1/evaluations/")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_evaluations_list_allows_with_evals_read(monkeypatch):
    principal = AuthPrincipal(
        kind="user",
        user_id=1,
        api_key_id=None,
        subject=None,
        token_type="access",
        jti=None,
        roles=["user"],
        permissions=["evals.read"],
        is_admin=False,
        org_ids=[],
        team_ids=[],
    )
    app = _build_app_with_overrides(principal)

    async def _fake_service_for_user(_user_id: int):
        class _Svc:
            async def list_evaluations(
                self,
                *,
                limit: int,
                after: str | None,
                eval_type: str | None,
                created_by: Any,
            ):
                _ = (limit, after, eval_type, created_by)
                return [], False

        return _Svc()

    from tldw_Server_API.app.core.Evaluations import unified_evaluation_service as ues

    monkeypatch.setattr(ues, "get_unified_evaluation_service_for_user", _fake_service_for_user)

    with TestClient(app) as client:
        resp = client.get("/api/v1/evaluations/")
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("object") == "list"
    assert isinstance(body.get("data"), list)


@pytest.mark.asyncio
async def test_evaluations_admin_cleanup_respects_require_admin(monkeypatch):
    """
    Sanity check that require_admin rejects a non-admin user when the EVALS_HEAVY_ADMIN_ONLY
    guard is enabled. This exercises the gating helper directly rather than the full
    HTTP stack, which also depends on AUTH_MODE and bootstrap state.
    """
    from fastapi import HTTPException
    from tldw_Server_API.app.api.v1.endpoints.evaluations_auth import require_admin

    user = SimpleNamespace(is_admin=False)
    monkeypatch.setenv("EVALS_HEAVY_ADMIN_ONLY", "true")
    with pytest.raises(HTTPException) as excinfo:
        require_admin(user)
    assert excinfo.value.status_code == 403
