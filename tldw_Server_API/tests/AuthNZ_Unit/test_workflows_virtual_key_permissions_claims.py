from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Optional

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.api.v1.endpoints import workflows as wf_mod
from tldw_Server_API.app.core.AuthNZ.permissions import WORKFLOWS_ADMIN
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthContext, AuthPrincipal


def _make_principal(
    *,
    kind: str = "user",
    is_admin: bool = False,
    roles: Optional[list[str]] = None,
    permissions: Optional[list[str]] = None,
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


def _build_app_with_overrides(
    principal: Optional[AuthPrincipal],
    *,
    fail_with_401: bool = False,
) -> FastAPI:
    app = FastAPI()
    app.include_router(wf_mod.router)

    async def _fake_get_auth_principal(request: Request) -> AuthPrincipal:  # type: ignore[override]
        if fail_with_401:
            raise HTTPException(
                status_code=401,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        assert principal is not None, "principal must be provided when fail_with_401 is False"
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
            username="wf-user",
            is_active=True,
            roles=list(principal.roles) if principal else [],
            permissions=list(principal.permissions) if principal else [],
            is_admin=principal.is_admin if principal else False,
            tenant_id="default",
        )

    app.dependency_overrides[wf_mod.get_request_user] = _fake_get_request_user

    return app


@pytest.mark.unit
def test_workflows_virtual_key_401_when_principal_unavailable(monkeypatch):
     from tldw_Server_API.app.core.AuthNZ import settings as settings_mod

    monkeypatch.setenv("AUTH_MODE", "multi_user")
    settings_mod.reset_settings()

    app = _build_app_with_overrides(principal=None, fail_with_401=True)

    with TestClient(app) as client:
        resp = client.post("/api/v1/workflows/auth/virtual-key", json={"ttl_minutes": 60, "scope": "workflows"})

    assert resp.status_code == 401
    assert "Authentication required" in resp.json().get("detail", "")


@pytest.mark.unit
def test_workflows_virtual_key_403_when_missing_admin_permissions(monkeypatch):
     from tldw_Server_API.app.core.AuthNZ import settings as settings_mod

    monkeypatch.setenv("AUTH_MODE", "multi_user")
    settings_mod.reset_settings()

    principal = _make_principal(
        is_admin=False,
        roles=["user"],
        permissions=[],  # Missing WORKFLOWS_ADMIN
    )
    app = _build_app_with_overrides(principal=principal)

    with TestClient(app) as client:
        resp = client.post("/api/v1/workflows/auth/virtual-key", json={"ttl_minutes": 60, "scope": "workflows"})

    assert resp.status_code == 403


@pytest.mark.unit
def test_workflows_virtual_key_400_when_not_multi_user_mode(monkeypatch):
     from tldw_Server_API.app.core.AuthNZ import settings as settings_mod

    monkeypatch.setenv("AUTH_MODE", "single_user")
    settings_mod.reset_settings()

    principal = _make_principal(
        is_admin=True,
        roles=["admin"],
        permissions=[WORKFLOWS_ADMIN],
    )
    app = _build_app_with_overrides(principal=principal)

    with TestClient(app) as client:
        resp = client.post("/api/v1/workflows/auth/virtual-key", json={"ttl_minutes": 60, "scope": "workflows"})

    assert resp.status_code == 400
    assert "Virtual keys only apply in multi-user mode" in resp.json().get("detail", "")


@pytest.mark.unit
def test_workflows_virtual_key_200_for_admin_with_workflows_admin_permission(monkeypatch):
     from tldw_Server_API.app.core.AuthNZ import settings as settings_mod

    monkeypatch.setenv("AUTH_MODE", "multi_user")
    settings_mod.reset_settings()

    principal = _make_principal(
        is_admin=True,
        roles=["admin"],
        permissions=[WORKFLOWS_ADMIN],
    )
    app = _build_app_with_overrides(principal=principal)

    with TestClient(app) as client:
        resp = client.post("/api/v1/workflows/auth/virtual-key", json={"ttl_minutes": 30, "scope": "workflows"})

    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert data.get("scope") == "workflows"
