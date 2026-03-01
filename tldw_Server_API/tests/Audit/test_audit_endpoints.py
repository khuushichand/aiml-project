from contextlib import asynccontextmanager

import httpx
import pytest
from starlette.requests import Request

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import get_audit_service_for_user
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthContext, AuthPrincipal


class _StubAuditService:
    async def export_events(self, **_kwargs):
        return "[]"

    async def count_events(self, **_kwargs):
        return 0


def _make_admin_principal() -> AuthPrincipal:
    return AuthPrincipal(
        kind="user",
        user_id=1,
        api_key_id=None,
        subject="single-user",
        token_type="single_user",
        jti=None,
        roles=["admin"],
        permissions=["system.logs"],
        is_admin=True,
        org_ids=[],
        team_ids=[],
    )


def _override_principal(app, principal: AuthPrincipal) -> None:
    async def _fake_get_auth_principal(request: Request) -> AuthPrincipal:  # type: ignore[override]
        request.state.auth = AuthContext(
            principal=principal,
            ip=None,
            user_agent=None,
            request_id=None,
        )
        return principal

    app.dependency_overrides[auth_deps.get_auth_principal] = _fake_get_auth_principal


@asynccontextmanager
async def _get_client(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "true")
    from tldw_Server_API.app.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=None) as client:  # nosec B113
        try:
            yield client, app
        finally:
            app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_audit_export_rejects_invalid_event_type(monkeypatch):
    async with _get_client(monkeypatch) as (client, app):
        from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user

        async def _override_audit_service(current_user=None):
            return _StubAuditService()

        app.dependency_overrides[get_request_user] = lambda: User(id=1, username="admin", is_active=True)
        app.dependency_overrides[get_audit_service_for_user] = _override_audit_service
        _override_principal(app, _make_admin_principal())

        resp = await client.get(
            "/api/v1/audit/export",
            params={"event_type": "not.a.valid.type"},
            headers={"X-API-KEY": "test-api-key-12345"},
        )
        assert resp.status_code == 400
        assert "Invalid event_type" in resp.json().get("detail", "")


@pytest.mark.asyncio
async def test_audit_count_rejects_invalid_category(monkeypatch):
    async with _get_client(monkeypatch) as (client, app):
        from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user

        async def _override_audit_service(current_user=None):
            return _StubAuditService()

        app.dependency_overrides[get_request_user] = lambda: User(id=1, username="admin", is_active=True)
        app.dependency_overrides[get_audit_service_for_user] = _override_audit_service
        _override_principal(app, _make_admin_principal())

        resp = await client.get(
            "/api/v1/audit/count",
            params={"category": "not_a_category"},
            headers={"X-API-KEY": "test-api-key-12345"},
        )
        assert resp.status_code == 400
        assert "Invalid category" in resp.json().get("detail", "")
