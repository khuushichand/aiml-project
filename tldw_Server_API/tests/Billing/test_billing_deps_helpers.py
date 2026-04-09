"""
Unit tests for get_billing_org_id and resolve_org_id_for_principal helpers.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException, Response

from tldw_Server_API.app.api.v1.API_Deps import billing_deps
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal


# ---------------------------------------------------------------------------
# get_billing_org_id
# ---------------------------------------------------------------------------

class TestGetBillingOrgId:
    """Tests for the get_billing_org_id FastAPI dependency."""

    @pytest.mark.asyncio
    async def test_returns_none_when_enforcement_disabled(self, monkeypatch):
        """When LIMIT_ENFORCEMENT_ENABLED=false, returns None immediately."""
        monkeypatch.setenv("LIMIT_ENFORCEMENT_ENABLED", "false")
        principal = AuthPrincipal(kind="user", user_id=1, is_admin=False)
        result = await billing_deps.get_billing_org_id(
            principal=principal, x_tldw_org_id=None, org_id=None,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_resolved_org_id(self, monkeypatch):
        """When enforcement is on and org resolves, returns the org_id."""
        monkeypatch.setenv("LIMIT_ENFORCEMENT_ENABLED", "true")

        async def _fake_resolve(principal, org_id=None, x_tldw_org_id=None):
            return 42

        monkeypatch.setattr(billing_deps, "_resolve_org_id", _fake_resolve, raising=False)
        principal = AuthPrincipal(kind="user", user_id=1, is_admin=False)
        result = await billing_deps.get_billing_org_id(
            principal=principal, x_tldw_org_id=None, org_id=None,
        )
        assert result == 42

    @pytest.mark.asyncio
    async def test_returns_none_on_http_error_when_orgless_allowed(self, monkeypatch):
        """When org resolution fails and orgless access is allowed, returns None."""
        monkeypatch.setenv("LIMIT_ENFORCEMENT_ENABLED", "true")
        monkeypatch.setattr(billing_deps, "_allow_orgless_billing_access", lambda: True, raising=False)

        async def _fail_resolve(principal, org_id=None, x_tldw_org_id=None):
            raise HTTPException(status_code=403, detail="No org")

        monkeypatch.setattr(billing_deps, "_resolve_org_id", _fail_resolve, raising=False)
        principal = AuthPrincipal(kind="user", user_id=1, is_admin=False)
        result = await billing_deps.get_billing_org_id(
            principal=principal, x_tldw_org_id=None, org_id=None,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_raises_when_orgless_not_allowed(self, monkeypatch):
        """When org resolution fails and orgless access is NOT allowed, raises."""
        monkeypatch.setenv("LIMIT_ENFORCEMENT_ENABLED", "true")
        monkeypatch.setattr(billing_deps, "_allow_orgless_billing_access", lambda: False, raising=False)

        async def _fail_resolve(principal, org_id=None, x_tldw_org_id=None):
            raise HTTPException(status_code=403, detail="No org")

        monkeypatch.setattr(billing_deps, "_resolve_org_id", _fail_resolve, raising=False)
        principal = AuthPrincipal(kind="user", user_id=1, is_admin=False)

        with pytest.raises(HTTPException) as exc_info:
            await billing_deps.get_billing_org_id(
                principal=principal, x_tldw_org_id=None, org_id=None,
            )
        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# resolve_org_id_for_principal
# ---------------------------------------------------------------------------

class TestResolveOrgIdForPrincipal:
    """Tests for the WebSocket-compatible resolve_org_id_for_principal helper."""

    @pytest.mark.asyncio
    async def test_returns_none_when_enforcement_disabled(self, monkeypatch):
        monkeypatch.setenv("LIMIT_ENFORCEMENT_ENABLED", "false")
        principal = AuthPrincipal(kind="user", user_id=1, is_admin=False)
        result = await billing_deps.resolve_org_id_for_principal(principal)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_resolved_org_id(self, monkeypatch):
        monkeypatch.setenv("LIMIT_ENFORCEMENT_ENABLED", "true")

        async def _fake_resolve(principal, org_id=None, x_tldw_org_id=None):
            return 99

        monkeypatch.setattr(billing_deps, "_resolve_org_id", _fake_resolve, raising=False)
        principal = AuthPrincipal(kind="user", user_id=1, is_admin=False)
        result = await billing_deps.resolve_org_id_for_principal(principal)
        assert result == 99

    @pytest.mark.asyncio
    async def test_returns_none_on_generic_exception(self, monkeypatch):
        """Generic exceptions are caught and return None (fail-open)."""
        monkeypatch.setenv("LIMIT_ENFORCEMENT_ENABLED", "true")
        monkeypatch.setattr(billing_deps, "_allow_orgless_billing_access", lambda: False, raising=False)

        async def _fail_resolve(principal, org_id=None, x_tldw_org_id=None):
            raise RuntimeError("DB unavailable")

        monkeypatch.setattr(billing_deps, "_resolve_org_id", _fail_resolve, raising=False)
        principal = AuthPrincipal(kind="user", user_id=1, is_admin=False)
        result = await billing_deps.resolve_org_id_for_principal(principal)
        assert result is None
