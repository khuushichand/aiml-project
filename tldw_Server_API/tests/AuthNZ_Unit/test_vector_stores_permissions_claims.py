from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.api.v1.endpoints import vector_stores_openai as vs_mod
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthContext, AuthPrincipal


def _make_principal(
    *,
    kind: str = "user",
    is_admin: bool = False,
    roles: list[str] | None = None,
    permissions: list[str] | None = None,
) -> AuthPrincipal:
    return AuthPrincipal(
        kind=kind,
        user_id=1,
        api_key_id=None,
        subject=None,
        token_type="access",
        jti=None,
        roles=roles or [],
        permissions=permissions or [],
        is_admin=is_admin,
        org_ids=[],
        team_ids=[],
    )


def _build_app_with_overrides(principal: AuthPrincipal) -> FastAPI:
    app = FastAPI()
    app.include_router(vs_mod.router)

    async def _fake_get_auth_principal(request: Request) -> AuthPrincipal:  # type: ignore[override]
        ip = request.client.host if getattr(request, "client", None) else None
        ua = request.headers.get("User-Agent") if getattr(request, "headers", None) else None
        request_id = request.headers.get("X-Request-ID") if getattr(request, "headers", None) else None
        request.state.auth = AuthContext(
            principal=principal,
            ip=ip,
            user_agent=ua,
            request_id=request_id,
        )
        return principal

    app.dependency_overrides[auth_deps.get_auth_principal] = _fake_get_auth_principal

    async def _fake_get_request_user():
        return SimpleNamespace(
            id=1,
            username="vector-admin",
            is_active=True,
            roles=list(principal.roles),
            permissions=list(principal.permissions),
            is_admin=principal.is_admin,
        )

    app.dependency_overrides[vs_mod.get_request_user] = _fake_get_request_user

    class _FakeAdapter:
        async def initialize(self):
            return None

        async def health(self):
            return {"ok": True}

    async def _fake_get_adapter_for_user(_user, _dim):
        return _FakeAdapter()

    app.dependency_overrides[vs_mod._get_adapter_for_user] = _fake_get_adapter_for_user
    return app


@pytest.mark.asyncio
async def test_vector_stores_admin_health_forbidden_without_admin_role():
    principal = _make_principal(roles=["user"], permissions=[], is_admin=False)
    app = _build_app_with_overrides(principal)

    with TestClient(app) as client:
        resp = client.get("/vector_stores/admin/health")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_vector_stores_admin_health_allowed_with_admin_role():
    principal = _make_principal(roles=["admin"], permissions=[], is_admin=True)
    app = _build_app_with_overrides(principal)

    with TestClient(app) as client:
        resp = client.get("/vector_stores/admin/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("ok") is True

