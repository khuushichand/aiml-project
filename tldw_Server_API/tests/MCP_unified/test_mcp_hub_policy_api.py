from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest
from starlette.requests import Request

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.api.v1.endpoints import mcp_hub_management
from tldw_Server_API.app.core.AuthNZ.permissions import SYSTEM_CONFIGURE
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal


def _make_principal(
    *,
    roles: list[str] | None = None,
    permissions: list[str] | None = None,
) -> AuthPrincipal:
    return AuthPrincipal(
        kind="user",
        user_id=7,
        api_key_id=None,
        subject="7",
        token_type="access",
        jti=None,
        roles=roles or [],
        permissions=permissions or [],
        is_admin=False,
        org_ids=[],
        team_ids=[],
    )


class _FakePolicyService:
    async def create_permission_profile(self, **kwargs):
        return {
            "id": 5,
            "name": kwargs["name"],
            "description": kwargs.get("description"),
            "owner_scope_type": kwargs["owner_scope_type"],
            "owner_scope_id": kwargs.get("owner_scope_id"),
            "mode": kwargs["mode"],
            "policy_document": kwargs["policy_document"],
            "is_active": kwargs.get("is_active", True),
            "created_by": kwargs.get("actor_id"),
            "updated_by": kwargs.get("actor_id"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def create_policy_assignment(self, **kwargs):
        return {
            "id": 11,
            "target_type": kwargs["target_type"],
            "target_id": kwargs.get("target_id"),
            "owner_scope_type": kwargs["owner_scope_type"],
            "owner_scope_id": kwargs.get("owner_scope_id"),
            "profile_id": kwargs.get("profile_id"),
            "inline_policy_document": kwargs["inline_policy_document"],
            "approval_policy_id": kwargs.get("approval_policy_id"),
            "is_active": kwargs.get("is_active", True),
            "created_by": kwargs.get("actor_id"),
            "updated_by": kwargs.get("actor_id"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }


def _build_app(principal: AuthPrincipal) -> FastAPI:
    app = FastAPI()
    app.include_router(mcp_hub_management.router, prefix="/api/v1")

    async def _fake_get_auth_principal(_request: Request) -> AuthPrincipal:  # type: ignore[override]
        return principal

    app.dependency_overrides[auth_deps.get_auth_principal] = _fake_get_auth_principal
    app.dependency_overrides[mcp_hub_management.get_mcp_hub_service] = lambda: _FakePolicyService()
    return app


def test_create_permission_profile_requires_grant_authority_for_capabilities() -> None:
    app = _build_app(
        _make_principal(
            roles=[],
            permissions=[SYSTEM_CONFIGURE],
        )
    )

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/mcp/hub/permission-profiles",
            json={
                "name": "Process Exec",
                "owner_scope_type": "user",
                "owner_scope_id": 7,
                "mode": "custom",
                "policy_document": {"capabilities": ["process.execute"]},
                "is_active": True,
            },
        )

    assert resp.status_code == 403
    assert "grant.process.execute" in resp.json()["detail"]


def test_create_permission_profile_returns_created_payload_when_grant_is_present() -> None:
    app = _build_app(
        _make_principal(
            roles=[],
            permissions=[SYSTEM_CONFIGURE, "grant.process.execute"],
        )
    )

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/mcp/hub/permission-profiles",
            json={
                "name": "Process Exec",
                "owner_scope_type": "user",
                "owner_scope_id": 7,
                "mode": "custom",
                "policy_document": {"capabilities": ["process.execute"]},
                "is_active": True,
            },
        )

    assert resp.status_code == 201
    payload = resp.json()
    assert payload["name"] == "Process Exec"
    assert payload["policy_document"]["capabilities"] == ["process.execute"]
    assert payload["owner_scope_type"] == "user"


def test_create_policy_assignment_returns_created_payload() -> None:
    app = _build_app(
        _make_principal(
            roles=[],
            permissions=[SYSTEM_CONFIGURE, "grant.process.execute"],
        )
    )

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/mcp/hub/policy-assignments",
            json={
                "target_type": "persona",
                "target_id": "researcher",
                "owner_scope_type": "user",
                "owner_scope_id": 7,
                "profile_id": None,
                "inline_policy_document": {"capabilities": ["process.execute"]},
                "approval_policy_id": None,
                "is_active": True,
            },
        )

    assert resp.status_code == 201
    payload = resp.json()
    assert payload["target_type"] == "persona"
    assert payload["target_id"] == "researcher"
    assert payload["inline_policy_document"]["capabilities"] == ["process.execute"]
