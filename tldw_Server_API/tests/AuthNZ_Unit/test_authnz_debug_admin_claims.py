from typing import Optional

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.api.v1.endpoints import authnz_debug as debug_mod
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal


def _build_app_with_overrides(
    principal: Optional[AuthPrincipal],
    *,
    fail_with_401: bool = False,
) -> FastAPI:
    app = FastAPI()
    app.include_router(debug_mod.router, prefix="/api/v1")

    async def _fake_get_auth_principal(request: Request) -> AuthPrincipal:  # type: ignore[override]
        if fail_with_401:
            raise HTTPException(
                status_code=401,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        assert principal is not None
        return principal

    app.dependency_overrides[auth_deps.get_auth_principal] = _fake_get_auth_principal
    return app


def _make_principal(*, is_admin: bool, roles: Optional[list[str]] = None) -> AuthPrincipal:
    return AuthPrincipal(
        kind="user",
        user_id=1,
        api_key_id=None,
        subject=None,
        token_type="access",
        jti=None,
        roles=roles or [],
        permissions=[],
        is_admin=is_admin,
        org_ids=[],
        team_ids=[],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    ["/api/v1/authnz/debug/api-key-id", "/api/v1/authnz/debug/budget-summary"],
)
async def test_authnz_debug_401_when_principal_missing(path: str):
    app = _build_app_with_overrides(principal=None, fail_with_401=True)

    with TestClient(app) as client:
        resp = client.get(path)

    assert resp.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    ["/api/v1/authnz/debug/api-key-id", "/api/v1/authnz/debug/budget-summary"],
)
async def test_authnz_debug_403_when_not_admin(path: str):
    principal = _make_principal(is_admin=False, roles=["user"])
    app = _build_app_with_overrides(principal=principal)

    with TestClient(app) as client:
        resp = client.get(path)

    assert resp.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    ["/api/v1/authnz/debug/api-key-id", "/api/v1/authnz/debug/budget-summary"],
)
async def test_authnz_debug_200_for_admin(path: str):
    principal = _make_principal(is_admin=True, roles=["admin"])
    app = _build_app_with_overrides(principal=principal)

    with TestClient(app) as client:
        resp = client.get(path)

    assert resp.status_code == 200
