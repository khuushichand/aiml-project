from typing import Any

import pytest
from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import (
    require_permissions,
    require_roles,
    require_service_principal,
)
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal


app = FastAPI()


@app.get("/perm-protected")
async def perm_protected(
    _principal: AuthPrincipal = Depends(require_permissions("media.read")),
) -> dict[str, Any]:
    return {"status": "ok"}


@app.get("/service-protected")
async def service_protected(
    _principal: AuthPrincipal = Depends(require_service_principal),
) -> dict[str, Any]:
    return {"status": "ok-service"}


@app.get("/role-protected")
async def role_protected(
    _principal: AuthPrincipal = Depends(require_roles("admin")),
) -> dict[str, Any]:
    return {"status": "ok"}


router = APIRouter(
    dependencies=[
        Depends(require_roles("admin")),
        Depends(require_permissions("system.configure")),
    ]
)


@router.get("/router-guarded")
async def router_guarded() -> dict[str, Any]:
    return {"status": "router-ok"}


app.include_router(router)


client = TestClient(app)


def _make_principal(
    *,
    is_admin: bool = False,
    roles: list[str] | None = None,
    permissions: list[str] | None = None,
    kind: str = "user",
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


@pytest.mark.asyncio
async def test_require_permissions_http_401_when_principal_unavailable(monkeypatch):
    async def _fail_get_auth_principal(request):  # type: ignore[override]
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    monkeypatch.setattr(
        auth_deps, "_resolve_auth_principal", _fail_get_auth_principal, raising=True
    )

    resp = client.get("/perm-protected")
    assert resp.status_code == 401
    assert "Authentication required" in resp.json().get("detail", "")
    assert resp.headers.get("WWW-Authenticate") == "Bearer"


@pytest.mark.asyncio
async def test_require_roles_http_401_when_principal_unavailable(monkeypatch):
    async def _fail_get_auth_principal(request):  # type: ignore[override]
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    monkeypatch.setattr(
        auth_deps, "_resolve_auth_principal", _fail_get_auth_principal, raising=True
    )

    resp = client.get("/role-protected")
    assert resp.status_code == 401
    assert "Authentication required" in resp.json().get("detail", "")
    assert resp.headers.get("WWW-Authenticate") == "Bearer"


@pytest.mark.asyncio
async def test_require_permissions_http_403_when_missing_permission_adjusted(monkeypatch):
    async def _stub_get_auth_principal(request):  # type: ignore[override]
        return _make_principal(permissions=["media.other"], roles=["user"])

    monkeypatch.setattr(
        auth_deps, "_resolve_auth_principal", _stub_get_auth_principal, raising=True
    )

    local_client = TestClient(app)
    resp = local_client.get("/perm-protected")
    assert resp.status_code == 403
    assert "media.read" in resp.json().get("detail", "")


@pytest.mark.asyncio
async def test_router_dependencies_403_without_required_claims(monkeypatch):
    async def _stub_get_auth_principal(request):  # type: ignore[override]
        # Missing system.configure permission and admin role
        return _make_principal(permissions=["other.perm"], roles=["user"])

    monkeypatch.setattr(
        auth_deps, "_resolve_auth_principal", _stub_get_auth_principal, raising=True
    )

    resp = client.get("/router-guarded")
    assert resp.status_code == 403
    assert "Required role(s)" in resp.json().get("detail", "")


@pytest.mark.asyncio
async def test_router_dependencies_200_for_admin(monkeypatch):
    async def _stub_get_auth_principal(request):  # type: ignore[override]
        return _make_principal(is_admin=True, roles=["admin"], permissions=["system.configure"])

    monkeypatch.setattr(
        auth_deps, "_resolve_auth_principal", _stub_get_auth_principal, raising=True
    )

    resp = client.get("/router-guarded")
    assert resp.status_code == 200
    assert resp.json().get("status") == "router-ok"


@pytest.mark.asyncio
async def test_require_permissions_http_200_when_permission_present(monkeypatch):
    async def _stub_get_auth_principal(request):  # type: ignore[override]
        return _make_principal(permissions=["media.read"], roles=["user"])

    monkeypatch.setattr(
        auth_deps, "_resolve_auth_principal", _stub_get_auth_principal, raising=True
    )

    local_client = TestClient(app)
    resp = local_client.get("/perm-protected")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_require_roles_http_403_when_missing_role(monkeypatch):
    async def _stub_get_auth_principal(request):  # type: ignore[override]
        return _make_principal(roles=["user"], permissions=["media.read"])

    monkeypatch.setattr(
        auth_deps, "_resolve_auth_principal", _stub_get_auth_principal, raising=True
    )

    local_client = TestClient(app)
    resp = local_client.get("/role-protected")
    assert resp.status_code == 403
    assert "admin" in resp.json().get("detail", "")


@pytest.mark.asyncio
async def test_require_roles_http_200_when_role_present(monkeypatch):
    async def _stub_get_auth_principal(request):  # type: ignore[override]
        return _make_principal(roles=["admin"], permissions=["media.read"])

    monkeypatch.setattr(
        auth_deps, "_resolve_auth_principal", _stub_get_auth_principal, raising=True
    )

    local_client = TestClient(app)
    resp = local_client.get("/role-protected")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_require_roles_http_200_for_admin_claim_even_without_role(monkeypatch):
    async def _stub_get_auth_principal(request):  # type: ignore[override]
        return _make_principal(is_admin=False, roles=["user"], permissions=["*"])

    monkeypatch.setattr(
        auth_deps, "_resolve_auth_principal", _stub_get_auth_principal, raising=True
    )

    local_client = TestClient(app)
    resp = local_client.get("/role-protected")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_require_roles_http_403_for_boolean_admin_without_admin_claims(monkeypatch):
    async def _stub_get_auth_principal(request):  # type: ignore[override]
        return _make_principal(is_admin=True, roles=["user"], permissions=[])

    monkeypatch.setattr(
        auth_deps, "_resolve_auth_principal", _stub_get_auth_principal, raising=True
    )

    local_client = TestClient(app)
    resp = local_client.get("/role-protected")
    assert resp.status_code == 403
    assert "Required role" in resp.json().get("detail", "")


@pytest.mark.asyncio
async def test_require_permissions_respects_service_principal_with_claims(monkeypatch):
    async def _stub_get_auth_principal(request):  # type: ignore[override]
        return _make_principal(kind="service", permissions=["media.read"], roles=["worker"])

    monkeypatch.setattr(
        auth_deps, "_resolve_auth_principal", _stub_get_auth_principal, raising=True
    )

    local_client = TestClient(app)
    resp = local_client.get("/perm-protected")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_require_permissions_denies_anonymous_principal_without_claims(monkeypatch):
    async def _stub_get_auth_principal(request):  # type: ignore[override]
        return _make_principal(kind="anonymous", permissions=[], roles=[])

    monkeypatch.setattr(
        auth_deps, "_resolve_auth_principal", _stub_get_auth_principal, raising=True
    )

    local_client = TestClient(app)
    resp = local_client.get("/perm-protected")
    assert resp.status_code == 403
    assert "media.read" in resp.json().get("detail", "")


@pytest.mark.asyncio
async def test_require_service_principal_http_401_when_principal_unavailable(monkeypatch):
    async def _fail_get_auth_principal(request):  # type: ignore[override]
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    monkeypatch.setattr(
        auth_deps, "_resolve_auth_principal", _fail_get_auth_principal, raising=True
    )

    resp = client.get("/service-protected")
    assert resp.status_code == 401
    body = resp.json()
    assert "Authentication required" in body.get("detail", "")
    assert resp.headers.get("WWW-Authenticate") == "Bearer"


@pytest.mark.asyncio
async def test_require_service_principal_http_403_for_non_service_principal(monkeypatch):
    async def _stub_get_auth_principal(request):  # type: ignore[override]
        return _make_principal(kind="user", permissions=["media.read"], roles=["worker"])

    monkeypatch.setattr(
        auth_deps, "_resolve_auth_principal", _stub_get_auth_principal, raising=True
    )

    local_client = TestClient(app)
    resp = local_client.get("/service-protected")
    assert resp.status_code == 403
    assert "Service principal required" in resp.json().get("detail", "")


@pytest.mark.asyncio
async def test_require_service_principal_http_200_for_service_principal(monkeypatch):
    async def _stub_get_auth_principal(request):  # type: ignore[override]
        return _make_principal(kind="service", permissions=["media.read"], roles=["worker"])

    monkeypatch.setattr(
        auth_deps, "_resolve_auth_principal", _stub_get_auth_principal, raising=True
    )

    local_client = TestClient(app)
    resp = local_client.get("/service-protected")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok-service"}
