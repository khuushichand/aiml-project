from types import SimpleNamespace
from typing import Any, Dict, Optional

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.api.v1.endpoints import admin as admin_mod
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthContext, AuthPrincipal


def _build_app_with_overrides(
    principal: Optional[AuthPrincipal],
    *,
    fail_with_401: bool = False,
) -> FastAPI:
    app = FastAPI()
    app.include_router(admin_mod.router, prefix="/api/v1")

    async def _fake_get_auth_principal(request: Request) -> AuthPrincipal:  # type: ignore[override]
        if fail_with_401:
            raise HTTPException(
                status_code=401,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        assert principal is not None
        try:
            request.state.auth = AuthContext(
                principal=principal,
                ip="127.0.0.1",
                user_agent="pytest-agent",
                request_id="admin-single-user-test",
            )
        except Exception:
            pass
        return principal

    app.dependency_overrides[auth_deps.get_auth_principal] = _fake_get_auth_principal

    # Security alert dispatcher is used by the tested endpoint; stub it to avoid
    # dependence on real sinks or configuration.
    class _FakeDispatcher:
        def __init__(self) -> None:
            self._status: Dict[str, Any] = {
                "enabled": False,
                "min_severity": "high",
                "last_dispatch_time": None,
                "last_dispatch_success": None,
                "last_dispatch_error": None,
                "dispatch_count": 0,
                "last_validation_time": None,
                "last_validation_errors": [],
                "file_sink_configured": False,
                "webhook_configured": False,
                "email_configured": False,
                "last_sink_status": {},
                "last_sink_errors": {},
                "sink_thresholds": {},
                "sink_backoff_until": {},
            }

        def get_status(self) -> Dict[str, Any]:
            return self._status

    fake_dispatcher = _FakeDispatcher()
    app.dependency_overrides[admin_mod.get_security_alert_dispatcher] = lambda: fake_dispatcher

    return app


def _make_single_user_principal(
    *,
    is_admin: bool,
    roles: Optional[list[str]] = None,
    permissions: Optional[list[str]] = None,
) -> AuthPrincipal:
    return AuthPrincipal(
        kind="single_user",
        user_id=1,
        api_key_id=None,
        subject=None,
        token_type="api_key",
        jti=None,
        roles=roles or [],
        permissions=permissions or [],
        is_admin=is_admin,
        org_ids=[],
        team_ids=[],
    )


@pytest.mark.asyncio
async def test_admin_security_status_401_when_principal_unavailable():
    app = _build_app_with_overrides(principal=None, fail_with_401=True)

    with TestClient(app) as client:
        resp = client.get("/api/v1/admin/security/alert-status")

    assert resp.status_code == 401
    assert "Authentication required" in resp.json().get("detail", "")


@pytest.mark.asyncio
async def test_admin_security_status_403_for_single_user_without_admin_claims():
    principal = _make_single_user_principal(
        is_admin=False,
        roles=["user"],
        permissions=[],
    )
    app = _build_app_with_overrides(principal=principal)

    with TestClient(app) as client:
        resp = client.get("/api/v1/admin/security/alert-status")

    assert resp.status_code == 403
    assert "admin" in resp.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_admin_security_status_200_for_single_user_admin_principal():
    principal = _make_single_user_principal(
        is_admin=True,
        roles=["admin"],
        permissions=[],
    )
    app = _build_app_with_overrides(principal=principal)

    with TestClient(app) as client:
        resp = client.get("/api/v1/admin/security/alert-status")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body.get("enabled"), bool)
    assert isinstance(body.get("dispatch_count"), int)

