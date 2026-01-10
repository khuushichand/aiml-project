from __future__ import annotations

from typing import Optional

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.api.v1.endpoints import moderation as moderation_mod
from tldw_Server_API.app.core.AuthNZ.permissions import SYSTEM_CONFIGURE
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthContext, AuthPrincipal


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
    app.include_router(moderation_mod.router, prefix="/api/v1")

    async def _fake_get_auth_principal(request: Request) -> AuthPrincipal:  # type: ignore[override]
        if fail_with_401:
            raise HTTPException(
                status_code=401,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        assert principal is not None
        request.state.auth = AuthContext(
            principal=principal,
            ip=None,
            user_agent=None,
            request_id=None,
        )
        return principal

    app.dependency_overrides[auth_deps.get_auth_principal] = _fake_get_auth_principal

    class _StubModerationService:
        def list_user_overrides(self) -> dict:
                     return {}

    moderation_mod.get_moderation_service = lambda: _StubModerationService()  # type: ignore[assignment]

    return app


@pytest.mark.asyncio
async def test_moderation_users_401_when_principal_unavailable():
    app = _build_app(principal=None, fail_with_401=True)

    with TestClient(app) as client:
        resp = client.get("/api/v1/moderation/users")

    assert resp.status_code == 401
    assert "Authentication required" in resp.json().get("detail", "")


@pytest.mark.asyncio
async def test_moderation_users_403_without_admin_or_permission():
    principal = _make_principal(
        is_admin=False,
        roles=["user"],
        permissions=[],
    )
    app = _build_app(principal=principal)

    with TestClient(app) as client:
        resp = client.get("/api/v1/moderation/users")

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_moderation_users_200_for_admin_with_permission():
    principal = _make_principal(
        is_admin=True,
        roles=["admin"],
        permissions=[SYSTEM_CONFIGURE],
    )
    app = _build_app(principal=principal)

    with TestClient(app) as client:
        resp = client.get("/api/v1/moderation/users")

    assert resp.status_code == 200
    body = resp.json()
    assert body.get("overrides") == {}
