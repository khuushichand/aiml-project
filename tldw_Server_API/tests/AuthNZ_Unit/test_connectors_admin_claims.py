from __future__ import annotations

from typing import Any, Optional

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.api.v1.endpoints import connectors as connectors_mod
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthContext, AuthPrincipal
from tldw_Server_API.app.core.AuthNZ.permissions import SYSTEM_CONFIGURE


def _make_principal(
    *,
    is_admin: bool,
    roles: Optional[list[str]] = None,
    permissions: Optional[list[str]] = None,
) -> AuthPrincipal:
    return AuthPrincipal(
        kind="user",
        user_id=1,
        api_key_id=None,
        subject=None,
        token_type="access",
        jti=None,
        roles=roles or [],
        permissions=permissions or [],
        is_admin=is_admin,
        org_ids=[1],
        team_ids=[],
    )


def _build_app(
    principal: Optional[AuthPrincipal],
    *,
    fail_with_401: bool = False,
) -> FastAPI:
    app = FastAPI()
    app.include_router(connectors_mod.router, prefix="/api/v1")

    async def _fake_get_auth_principal(request: Request) -> AuthPrincipal:  # type: ignore[override]
        if fail_with_401:
            raise HTTPException(
                status_code=401,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        assert principal is not None
        request.state.auth = AuthContext(principal=principal, ip=None, user_agent=None, request_id=None)
        return principal

    app.dependency_overrides[auth_deps.get_auth_principal] = _fake_get_auth_principal

    async def _fake_current_user() -> dict[str, Any]:
        return {"id": 1, "role": "admin", "org_memberships": [{"org_id": 1}], "is_active": True}

    app.dependency_overrides[auth_deps.get_current_active_user] = _fake_current_user

    class _FakeDB:
        async def execute(self, *args: Any, **kwargs: Any) -> None:  # noqa: D401
            """No-op execute for DB dependency."""
            return None

    async def _fake_get_db():
        return _FakeDB()

    app.dependency_overrides[auth_deps.get_db_transaction] = _fake_get_db
    return app


@pytest.mark.asyncio
async def test_connectors_admin_policy_401(monkeypatch: pytest.MonkeyPatch):
    app = _build_app(principal=None, fail_with_401=True)
    with TestClient(app) as client:
        resp = client.get("/api/v1/connectors/admin/policy", params={"org_id": 1})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_connectors_admin_policy_403_without_admin(monkeypatch: pytest.MonkeyPatch):
    principal = _make_principal(is_admin=False, roles=["user"], permissions=[])
    app = _build_app(principal=principal)
    with TestClient(app) as client:
        resp = client.get("/api/v1/connectors/admin/policy", params={"org_id": 1})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_connectors_admin_policy_200_for_admin_with_perm(monkeypatch: pytest.MonkeyPatch):
    principal = _make_principal(is_admin=True, roles=["admin"], permissions=[SYSTEM_CONFIGURE])
    app = _build_app(principal=principal)

    async def _fake_get_policy(db, org_id):
        return {"org_id": org_id, "source": "test"}

    monkeypatch.setattr(connectors_mod, "get_policy", _fake_get_policy)

    with TestClient(app) as client:
        resp = client.get("/api/v1/connectors/admin/policy", params={"org_id": 1})
    assert resp.status_code == 200
    assert resp.json().get("org_id") == 1
