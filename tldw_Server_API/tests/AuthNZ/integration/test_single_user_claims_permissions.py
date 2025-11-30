import os
from pathlib import Path
from typing import Any, Dict

import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import (
    get_auth_principal,
    require_permissions,
    require_roles,
)
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


pytestmark = pytest.mark.integration


router = APIRouter()


@router.get("/single-user/whoami/user")
async def whoami_user(
    user: User = Depends(get_request_user),
) -> Dict[str, Any]:
    return {
        "id": user.id,
        "roles": list(user.roles or []),
        "permissions": list(user.permissions or []),
        "is_admin": bool(getattr(user, "is_admin", False)),
    }


@router.get("/single-user/protected/perm")
async def protected_by_permission(
    principal: AuthPrincipal = Depends(require_permissions("media.read")),
) -> Dict[str, Any]:
    return {
        "principal_id": principal.principal_id,
        "kind": principal.kind,
        "roles": principal.roles,
        "permissions": principal.permissions,
        "is_admin": principal.is_admin,
    }


@router.get("/single-user/protected/role")
async def protected_by_role(
    principal: AuthPrincipal = Depends(require_roles("admin")),
) -> Dict[str, Any]:
    return {
        "principal_id": principal.principal_id,
        "kind": principal.kind,
        "roles": principal.roles,
        "permissions": principal.permissions,
        "is_admin": principal.is_admin,
    }


def _build_single_user_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return app


@pytest.mark.asyncio
async def test_single_user_bootstrapped_admin_uses_claims_for_permissions(tmp_path, monkeypatch):
    # Configure single-user SQLite AuthNZ with an isolated DB file
    db_path = Path(tmp_path) / "users.db"
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("SINGLE_USER_API_KEY", "test_single_user_claims_key_123")
    monkeypatch.setenv("TEST_MODE", "true")

    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings, get_settings
    from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool, get_db_pool
    from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables
    from tldw_Server_API.app.core.AuthNZ.initialize import bootstrap_single_user_profile

    # Ensure settings and DB pool see the single-user profile and isolated DB
    reset_settings()
    await reset_db_pool()

    pool = await get_db_pool()
    ensure_authnz_tables(Path(pool.db_path))

    # Seed the single-user admin and primary key via the shared bootstrap helper
    ok_first = await bootstrap_single_user_profile()
    ok_second = await bootstrap_single_user_profile()
    assert ok_first is True
    assert ok_second is True

    settings = get_settings()
    single_user_key = settings.SINGLE_USER_API_KEY

    app = _build_single_user_app()
    client = TestClient(app)

    # Fetch the bootstrapped admin as a User via get_request_user
    resp_user = client.get(
        "/api/v1/single-user/whoami/user",
        headers={"X-API-KEY": single_user_key},
    )
    assert resp_user.status_code == 200
    user_payload = resp_user.json()
    assert user_payload["id"] == settings.SINGLE_USER_FIXED_ID
    assert "admin" in user_payload["roles"]
    # Single-user path exposes concrete permissions claims
    assert "media.read" in user_payload["permissions"]
    assert user_payload["is_admin"] is True

    # The same key should succeed on permission- and role-protected endpoints
    resp_perm = client.get(
        "/api/v1/single-user/protected/perm",
        headers={"X-API-KEY": single_user_key},
    )
    assert resp_perm.status_code == 200
    perm_payload = resp_perm.json()
    assert perm_payload["kind"] == "single_user"
    assert perm_payload["is_admin"] is True
    assert "media.read" in perm_payload["permissions"]

    resp_role = client.get(
        "/api/v1/single-user/protected/role",
        headers={"X-API-KEY": single_user_key},
    )
    assert resp_role.status_code == 200
    role_payload = resp_role.json()
    assert role_payload["kind"] == "single_user"
    assert role_payload["is_admin"] is True
    assert "admin" in role_payload["roles"]


@pytest.mark.asyncio
async def test_single_user_non_admin_principal_denied_on_role(tmp_path, monkeypatch):
    # Reuse the same single-user bootstrap flow but override get_auth_principal
    # to simulate a principal with limited claims.
    db_path = Path(tmp_path) / "users_limited_role.db"
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("SINGLE_USER_API_KEY", "test_single_user_claims_key_limited")
    monkeypatch.setenv("TEST_MODE", "true")

    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings, get_settings
    from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool, get_db_pool
    from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables
    from tldw_Server_API.app.core.AuthNZ.initialize import bootstrap_single_user_profile
    from fastapi import Request
    from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal, AuthContext

    reset_settings()
    await reset_db_pool()

    pool = await get_db_pool()
    ensure_authnz_tables(Path(pool.db_path))

    ok_first = await bootstrap_single_user_profile()
    ok_second = await bootstrap_single_user_profile()
    assert ok_first is True
    assert ok_second is True

    settings = get_settings()
    single_user_key = settings.SINGLE_USER_API_KEY

    async def _limited_principal(request: Request):
        principal = AuthPrincipal(
            kind="single_user",
            user_id=settings.SINGLE_USER_FIXED_ID,
            api_key_id=None,
            subject=None,
            token_type="api_key",
            jti=None,
            roles=["user"],
            permissions=[],
            is_admin=False,
            org_ids=[],
            team_ids=[],
        )
        try:
            request.state.auth = AuthContext(
                principal=principal,
                ip="127.0.0.1",
                user_agent="pytest-agent",
                request_id="single-user-limited",
            )
        except Exception:
            pass
        return principal

    app = _build_single_user_app()
    app.dependency_overrides[get_auth_principal] = _limited_principal
    client = TestClient(app)

    resp_role = client.get(
        "/api/v1/single-user/protected/role",
        headers={"X-API-KEY": single_user_key},
    )
    assert resp_role.status_code == 403


@pytest.mark.asyncio
async def test_single_user_non_admin_principal_denied_on_permission(tmp_path, monkeypatch):
    # Same setup as above, but exercise permission-based gating.
    db_path = Path(tmp_path) / "users_limited_perm.db"
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("SINGLE_USER_API_KEY", "test_single_user_claims_key_limited_perm")
    monkeypatch.setenv("TEST_MODE", "true")

    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings, get_settings
    from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool, get_db_pool
    from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables
    from tldw_Server_API.app.core.AuthNZ.initialize import bootstrap_single_user_profile
    from fastapi import Request
    from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal, AuthContext

    reset_settings()
    await reset_db_pool()

    pool = await get_db_pool()
    ensure_authnz_tables(Path(pool.db_path))

    ok_first = await bootstrap_single_user_profile()
    ok_second = await bootstrap_single_user_profile()
    assert ok_first is True
    assert ok_second is True

    settings = get_settings()
    single_user_key = settings.SINGLE_USER_API_KEY

    async def _limited_principal(request: Request):
        principal = AuthPrincipal(
            kind="single_user",
            user_id=settings.SINGLE_USER_FIXED_ID,
            api_key_id=None,
            subject=None,
            token_type="api_key",
            jti=None,
            roles=["user"],
            permissions=[],
            is_admin=False,
            org_ids=[],
            team_ids=[],
        )
        try:
            request.state.auth = AuthContext(
                principal=principal,
                ip="127.0.0.1",
                user_agent="pytest-agent",
                request_id="single-user-limited-perm",
            )
        except Exception:
            pass
        return principal

    app = _build_single_user_app()
    app.dependency_overrides[get_auth_principal] = _limited_principal
    client = TestClient(app)

    resp_perm = client.get(
        "/api/v1/single-user/protected/perm",
        headers={"X-API-KEY": single_user_key},
    )
    assert resp_perm.status_code == 403
