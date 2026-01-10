from __future__ import annotations

from typing import Optional

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.api.v1.endpoints import mlx as mlx_mod
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
    app.include_router(mlx_mod.router, prefix="/api/v1")

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

    async def _fake_check_rate_limit() -> None:
        # No-op to keep tests focused on RBAC behavior
        return

    app.dependency_overrides[auth_deps.check_rate_limit] = _fake_check_rate_limit
    app.dependency_overrides[mlx_mod.check_rate_limit] = _fake_check_rate_limit

    class _StubRegistry:
        def __init__(self) -> None:
                     self.loaded = False
            self.unloaded = False

        def load(self, *args, **kwargs):

                     self.loaded = True
            return {"status": "ok"}

        def unload(self):

                     self.unloaded = True
            return {"status": "unloaded"}

        def status(self):

                     return {"ok": True}

    def _get_stub_registry() -> _StubRegistry:

             return _StubRegistry()

    app.dependency_overrides[mlx_mod.get_mlx_registry] = _get_stub_registry

    return app


@pytest.mark.unit
def test_mlx_load_401_when_principal_unavailable():
     app = _build_app_with_overrides(principal=None, fail_with_401=True)

    with TestClient(app) as client:
        resp = client.post("/api/v1/llm/providers/mlx/load", json={})

    assert resp.status_code == 401
    assert "Authentication required" in resp.json().get("detail", "")


@pytest.mark.unit
def test_mlx_load_403_when_missing_admin_role():
     principal = _make_principal(
        is_admin=False,
        roles=["user"],
        permissions=[],
    )
    app = _build_app_with_overrides(principal=principal)

    with TestClient(app) as client:
        resp = client.post("/api/v1/llm/providers/mlx/load", json={})

    assert resp.status_code == 403


@pytest.mark.unit
def test_mlx_load_200_for_admin_principal(monkeypatch):
     principal = _make_principal(
        is_admin=True,
        roles=["admin"],
        permissions=[],
    )
    # Ensure a valid default model_path so internal helpers do not raise
    monkeypatch.setattr(mlx_mod, "_default_settings", lambda: {"model_path": "stub-model-path"})

    class _StubRegistry:
        def load(self, model_path=None, overrides=None):
                     return {"status": "ok", "model_path": model_path}

        def unload(self):

                     return {"status": "unloaded"}

        def status(self):

                     return {"ok": True}

    monkeypatch.setattr(mlx_mod, "get_mlx_registry", lambda: _StubRegistry())
    app = _build_app_with_overrides(principal=principal)

    with TestClient(app) as client:
        resp = client.post("/api/v1/llm/providers/mlx/load", json={})

    assert resp.status_code == 200
    body = resp.json()
    assert body.get("status") == "ok"
