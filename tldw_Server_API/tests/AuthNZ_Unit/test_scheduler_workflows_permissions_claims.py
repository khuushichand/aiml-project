from types import SimpleNamespace
from typing import Any, Dict

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.api.v1.endpoints import scheduler_workflows as sched_mod
from tldw_Server_API.app.core.AuthNZ.permissions import WORKFLOWS_ADMIN
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthContext, AuthPrincipal


def _build_app_with_overrides(principal: AuthPrincipal) -> FastAPI:
    app = FastAPI()
    app.include_router(sched_mod.router)

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
            username="wf-admin",
            is_active=True,
            roles=list(principal.roles),
            permissions=list(principal.permissions),
            is_admin=principal.is_admin,
            tenant_id="default",
        )

    app.dependency_overrides[sched_mod.get_request_user] = _fake_get_request_user

    async def _fake_require_token_scope(*_args, **_kwargs):
        return None

    app.dependency_overrides[
        auth_deps.require_token_scope(
            "workflows",
            require_if_present=True,
            endpoint_id="scheduler.workflows.admin_rescan",
        )
    ] = _fake_require_token_scope

    class _FakeScheduler:
        def __init__(self) -> None:
                     self.calls: Dict[str, Any] = {}
            self._aps = SimpleNamespace(get_jobs=lambda: [])

        async def _rescan_once(self):
            self.calls["rescan"] = True

    fake_scheduler = _FakeScheduler()

    def _get_workflows_scheduler():

             return fake_scheduler

    app.dependency_overrides[sched_mod.get_workflows_scheduler] = _get_workflows_scheduler

    # Attach for inspection in tests
    app.state._fake_scheduler = fake_scheduler
    return app


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


@pytest.mark.asyncio
async def test_scheduler_admin_rescan_forbidden_for_non_admin_without_claims(monkeypatch):
    principal = _make_principal(
        roles=["user"],
        permissions=[],
        is_admin=False,
    )
    app = _build_app_with_overrides(principal)
    fake_scheduler = app.state._fake_scheduler
    monkeypatch.setattr(sched_mod, "get_workflows_scheduler", lambda: fake_scheduler)

    with TestClient(app) as client:
        resp = client.post("/api/v1/scheduler/workflows/admin/rescan")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_scheduler_admin_rescan_allows_for_admin_principal(monkeypatch):
    principal = _make_principal(
        roles=["admin"],
        permissions=[],
        is_admin=True,
    )
    app = _build_app_with_overrides(principal)
    fake_scheduler = app.state._fake_scheduler
    monkeypatch.setattr(sched_mod, "get_workflows_scheduler", lambda: fake_scheduler)

    with TestClient(app) as client:
        resp = client.post("/api/v1/scheduler/workflows/admin/rescan")
    assert resp.status_code == 200
    assert resp.json().get("ok") is True
    assert getattr(app.state._fake_scheduler, "calls", {}).get("rescan") is True


@pytest.mark.asyncio
async def test_scheduler_admin_rescan_allows_service_admin_principal(monkeypatch):
    principal = _make_principal(
        kind="service",
        roles=["worker"],
        permissions=[],
        is_admin=True,
    )
    app = _build_app_with_overrides(principal)
    fake_scheduler = app.state._fake_scheduler
    monkeypatch.setattr(sched_mod, "get_workflows_scheduler", lambda: fake_scheduler)

    with TestClient(app) as client:
        resp = client.post("/api/v1/scheduler/workflows/admin/rescan")
    assert resp.status_code == 200
    assert resp.json().get("ok") is True
    assert getattr(app.state._fake_scheduler, "calls", {}).get("rescan") is True


@pytest.mark.asyncio
async def test_scheduler_admin_rescan_allows_non_admin_with_workflows_admin_permission(monkeypatch):
    principal = _make_principal(
        roles=["user"],
        permissions=[WORKFLOWS_ADMIN],
        is_admin=False,
    )
    app = _build_app_with_overrides(principal)
    fake_scheduler = app.state._fake_scheduler
    monkeypatch.setattr(sched_mod, "get_workflows_scheduler", lambda: fake_scheduler)

    with TestClient(app) as client:
        resp = client.post("/api/v1/scheduler/workflows/admin/rescan")
    assert resp.status_code == 200
    assert resp.json().get("ok") is True
    assert getattr(app.state._fake_scheduler, "calls", {}).get("rescan") is True
