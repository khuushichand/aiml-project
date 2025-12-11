from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.api.v1.endpoints import embeddings_v5_production_enhanced as emb_mod
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
    app.include_router(emb_mod.router)

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
            username="emb-admin",
            is_active=True,
            roles=list(principal.roles),
            permissions=list(principal.permissions),
            is_admin=principal.is_admin,
        )

    app.dependency_overrides[emb_mod.get_request_user] = _fake_get_request_user
    return app


@pytest.mark.asyncio
async def test_embeddings_model_warmup_forbidden_without_admin_role():
    principal = _make_principal(roles=["user"], permissions=[], is_admin=False)
    app = _build_app_with_overrides(principal)

    with TestClient(app) as client:
        resp = client.post(
            "/embeddings/models/warmup",
            json={"model": "text-embedding-3-small"},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_embeddings_model_warmup_forbidden_with_permission_but_no_admin_role():
    # User has a relevant permission but lacks the admin role; require_roles("admin")
    # should still enforce the role-based guard.
    principal = _make_principal(
        roles=["user"],
        permissions=["system.configure"],
        is_admin=False,
    )
    app = _build_app_with_overrides(principal)

    with TestClient(app) as client:
        resp = client.post(
            "/embeddings/models/warmup",
            json={"model": "text-embedding-3-small"},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_embeddings_model_warmup_allowed_with_admin_role(monkeypatch):
    principal = _make_principal(roles=["admin"], permissions=[], is_admin=True)
    app = _build_app_with_overrides(principal)

    async def _fake_create_embeddings_batch_async(*_args, **_kwargs):
        return [[0.1, 0.2]]

    monkeypatch.setattr(
        emb_mod,
        "create_embeddings_batch_async",
        _fake_create_embeddings_batch_async,
    )

    with TestClient(app) as client:
        resp = client.post(
            "/embeddings/models/warmup",
            json={"model": "text-embedding-3-small"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("warmed") is True
