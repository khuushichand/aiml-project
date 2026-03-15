"""Tests for admin tenant provisioning endpoint."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.endpoints.admin.admin_tenant_provisioning import (
    TenantProvisionRequest,
    TenantProvisionResponse,
    router,
)
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal


def _admin_principal() -> AuthPrincipal:
    return AuthPrincipal(
        kind="user",
        user_id=1,
        username="admin",
        roles=["admin"],
        is_admin=True,
    )


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/admin")
    return app


class TestTenantProvisionRequest:
    def test_valid_request(self):
        req = TenantProvisionRequest(
            username="newuser",
            email="new@example.com",
            password="securepass123",
            org_name="NewOrg",
        )
        assert req.role == "owner"

    def test_custom_role(self):
        req = TenantProvisionRequest(
            username="newuser",
            email="new@example.com",
            password="securepass123",
            org_name="NewOrg",
            role="member",
        )
        assert req.role == "member"

    def test_password_too_short(self):
        with pytest.raises(Exception):
            TenantProvisionRequest(
                username="u",
                email="e@x.com",
                password="short",
                org_name="Org",
            )


class TestTenantProvisionResponse:
    def test_default_message(self):
        resp = TenantProvisionResponse(
            user_id=1,
            username="user",
            org_id=10,
            org_name="Org",
            role="owner",
        )
        assert resp.message == "Tenant provisioned successfully"


class TestProvisionEndpointUnit:
    """Unit tests for the provision_tenant endpoint logic using mocks."""

    @pytest.mark.asyncio
    async def test_provision_calls_steps(self):
        """Verify the endpoint function orchestrates user+org+member creation."""
        from tldw_Server_API.app.api.v1.endpoints.admin.admin_tenant_provisioning import (
            provision_tenant,
        )

        payload = TenantProvisionRequest(
            username="tenant_user",
            email="tenant@example.com",
            password="securepass123",
            org_name="TenantOrg",
        )
        principal = _admin_principal()

        # Build mock connection & pool
        mock_cursor = AsyncMock()
        # Sequence: check user exists (None), insert user (rowid=42), insert org (rowid=10), insert member
        mock_cursor.fetchone = AsyncMock(side_effect=[
            None,       # user not found
            (42,),      # last_insert_rowid for user
            (10,),      # last_insert_rowid for org
        ])

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=mock_conn)

        mock_pw_svc = MagicMock()
        mock_pw_svc.hash_password = MagicMock(return_value="hashed_pw")

        with patch(
            "tldw_Server_API.app.core.AuthNZ.database.get_db_pool",
            new_callable=AsyncMock,
            return_value=mock_pool,
        ), patch(
            "tldw_Server_API.app.core.AuthNZ.password_service.get_password_service",
            return_value=mock_pw_svc,
        ):
            result = await provision_tenant(payload, principal)

        assert result.user_id == 42
        assert result.org_id == 10
        assert result.username == "tenant_user"
        assert result.org_name == "TenantOrg"
        assert result.role == "owner"
