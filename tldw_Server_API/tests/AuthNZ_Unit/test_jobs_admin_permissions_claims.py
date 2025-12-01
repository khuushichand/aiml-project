from __future__ import annotations

from typing import Any, Optional

import os
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.api.v1.endpoints import jobs_admin as jobs_mod
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
    app.include_router(jobs_mod.router, prefix="/api/v1")

    async def _fake_get_auth_principal(request: Request) -> AuthPrincipal:  # type: ignore[override]
        if fail_with_401:
            raise HTTPException(
                status_code=401,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        assert principal is not None
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

    async def _fake_require_admin() -> Any:
        # Jobs admin endpoints expect a user-like object/dict; keep it minimal.
        return {"id": 1, "username": "admin"}

    app.dependency_overrides[auth_deps.require_admin] = _fake_require_admin

    # Patch JobManager to avoid touching a real DB in these tests
    class _FakeJobManager:
        def __init__(self, backend: Optional[str] = None, db_url: Optional[str] = None) -> None:
            self.backend = backend
            self.db_url = db_url

        def _get_queue_flags(self, domain: str, queue: str) -> dict:
            return {"paused": False, "drain": False}

    jobs_mod.JobManager = _FakeJobManager  # type: ignore[assignment]

    # Ensure domain-scoped RBAC does not inject additional 403s in these tests
    os.environ.pop("JOBS_DOMAIN_SCOPED_RBAC", None)
    os.environ.pop("JOBS_RBAC_FORCE", None)

    return app


@pytest.mark.asyncio
async def test_jobs_queue_status_401_when_principal_unavailable():
    app = _build_app_with_overrides(principal=None, fail_with_401=True)

    with TestClient(app) as client:
        resp = client.get("/api/v1/jobs/queue/status", params={"domain": "ps", "queue": "default"})

    assert resp.status_code == 401
    assert "Authentication required" in resp.json().get("detail", "")


@pytest.mark.asyncio
async def test_jobs_queue_status_403_when_missing_admin_role():
    principal = _make_principal(
        is_admin=False,
        roles=["user"],
        permissions=[],
    )
    app = _build_app_with_overrides(principal=principal)

    with TestClient(app) as client:
        resp = client.get("/api/v1/jobs/queue/status", params={"domain": "ps", "queue": "default"})

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_jobs_queue_status_200_for_admin_principal():
    principal = _make_principal(
        is_admin=True,
        roles=["admin"],
        permissions=[],
    )
    app = _build_app_with_overrides(principal=principal)

    with TestClient(app) as client:
        resp = client.get("/api/v1/jobs/queue/status", params={"domain": "ps", "queue": "default"})

    assert resp.status_code == 200
    body = resp.json()
    assert body.get("paused") is False
    assert body.get("drain") is False


@pytest.mark.asyncio
async def test_jobs_queue_status_403_when_domain_required_but_missing(monkeypatch: pytest.MonkeyPatch):
    principal = _make_principal(
        is_admin=True,
        roles=["admin"],
        permissions=[],
    )
    app = _build_app_with_overrides(principal=principal)

    # Enable domain-scoped RBAC and require a domain filter
    monkeypatch.setenv("JOBS_DOMAIN_SCOPED_RBAC", "1")
    monkeypatch.setenv("JOBS_REQUIRE_DOMAIN_FILTER", "1")

    with TestClient(app) as client:
        # Domain parameter is present but empty -> treated as missing/blank
        resp = client.get("/api/v1/jobs/queue/status", params={"domain": "", "queue": "default"})

    assert resp.status_code == 403
    detail = resp.json().get("detail", "")
    assert "Domain filter is required" in detail


@pytest.mark.asyncio
async def test_jobs_queue_status_403_when_domain_not_in_allowlist(monkeypatch: pytest.MonkeyPatch):
    principal = _make_principal(
        is_admin=True,
        roles=["admin"],
        permissions=[],
    )
    app = _build_app_with_overrides(principal=principal)

    # Enable domain-scoped RBAC with an allowlist that does not include requested domain
    monkeypatch.setenv("JOBS_DOMAIN_SCOPED_RBAC", "1")
    monkeypatch.setenv("JOBS_DOMAIN_ALLOWLIST_1", "tenant-a,tenant-b")

    with TestClient(app) as client:
        resp = client.get("/api/v1/jobs/queue/status", params={"domain": "tenant-x", "queue": "default"})

    assert resp.status_code == 403
    detail = resp.json().get("detail", "")
    assert "Not allowed for domain tenant-x" in detail


@pytest.mark.asyncio
async def test_jobs_queue_status_200_when_domain_in_allowlist(monkeypatch: pytest.MonkeyPatch):
    principal = _make_principal(
        is_admin=True,
        roles=["admin"],
        permissions=[],
    )
    app = _build_app_with_overrides(principal=principal)

    # Enable domain-scoped RBAC with an allowlist that includes requested domain
    monkeypatch.setenv("JOBS_DOMAIN_SCOPED_RBAC", "1")
    monkeypatch.setenv("JOBS_DOMAIN_ALLOWLIST_1", "tenant-a,tenant-b")

    with TestClient(app) as client:
        resp = client.get("/api/v1/jobs/queue/status", params={"domain": "tenant-a", "queue": "default"})

    assert resp.status_code == 200
    body = resp.json()
    assert body.get("paused") is False
    assert body.get("drain") is False
