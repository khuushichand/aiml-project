from __future__ import annotations

from typing import Optional
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.api.v1.endpoints.admin import admin_personalization as personalization_mod
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
    app.include_router(personalization_mod.router, prefix="/api/v1/admin")

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

    async def _fake_check_rate_limit() -> None:
        return

    app.dependency_overrides[auth_deps.get_auth_principal] = _fake_get_auth_principal
    app.dependency_overrides[auth_deps.check_rate_limit] = _fake_check_rate_limit
    app.dependency_overrides[personalization_mod.check_rate_limit] = _fake_check_rate_limit
    return app


@pytest.mark.unit
def test_admin_personalization_consolidate_401_when_principal_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        personalization_mod.admin_personalization_service,
        "trigger_consolidation",
        AsyncMock(return_value={"status": "ok"}),
    )

    app = _build_app_with_overrides(principal=None, fail_with_401=True)
    with TestClient(app) as client:
        resp = client.post("/api/v1/admin/personalization/consolidate", params={"user_id": "7"})

    assert resp.status_code == 401
    assert "Authentication required" in resp.json().get("detail", "")


@pytest.mark.unit
def test_admin_personalization_consolidate_403_when_missing_admin_role(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        personalization_mod.admin_personalization_service,
        "trigger_consolidation",
        AsyncMock(return_value={"status": "ok"}),
    )

    principal = _make_principal(is_admin=False, roles=["user"], permissions=[])
    app = _build_app_with_overrides(principal=principal)
    with TestClient(app) as client:
        resp = client.post("/api/v1/admin/personalization/consolidate", params={"user_id": "7"})

    assert resp.status_code == 403


@pytest.mark.unit
def test_admin_personalization_consolidate_200_for_admin_principal(monkeypatch: pytest.MonkeyPatch) -> None:
    consolidation_mock = AsyncMock(return_value={"status": "ok", "queued": True})
    monkeypatch.setattr(
        personalization_mod.admin_personalization_service,
        "trigger_consolidation",
        consolidation_mock,
    )

    principal = _make_principal(is_admin=True, roles=["admin"], permissions=[])
    app = _build_app_with_overrides(principal=principal)
    with TestClient(app) as client:
        resp = client.post("/api/v1/admin/personalization/consolidate", params={"user_id": "7"})

    assert resp.status_code == 200
    assert resp.json().get("status") == "ok"
    consolidation_mock.assert_awaited_once_with(user_id="7")
