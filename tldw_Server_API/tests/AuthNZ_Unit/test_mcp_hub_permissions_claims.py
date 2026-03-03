from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from starlette.requests import Request

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.api.v1.endpoints import mcp_hub_management as mcp_hub_mod
from tldw_Server_API.app.core.AuthNZ.permissions import SYSTEM_CONFIGURE
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal


class _FakeService:
    async def list_external_servers(self, **_kwargs: Any) -> list[dict[str, Any]]:
        return []

    async def create_external_server(self, **_kwargs: Any) -> dict[str, Any]:
        return {
            "id": "docs",
            "name": "Docs",
            "enabled": True,
            "owner_scope_type": "global",
            "owner_scope_id": None,
            "transport": "stdio",
            "config_json": "{}",
            "secret_configured": False,
            "key_hint": None,
            "created_by": 1,
            "updated_by": 1,
            "created_at": None,
            "updated_at": None,
        }


def _principal(*, roles: list[str] | None = None, permissions: list[str] | None = None) -> AuthPrincipal:
    return AuthPrincipal(
        kind="user",
        user_id=1,
        api_key_id=None,
        subject="1",
        token_type="access",
        jti=None,
        roles=roles or ["user"],
        permissions=permissions or [],
        is_admin=False,
        org_ids=[],
        team_ids=[],
    )


def _build_app(principal: AuthPrincipal) -> FastAPI:
    app = FastAPI()
    app.include_router(mcp_hub_mod.router, prefix="/api/v1")

    async def _fake_get_auth_principal(_request: Request) -> AuthPrincipal:  # type: ignore[override]
        return principal

    app.dependency_overrides[auth_deps.get_auth_principal] = _fake_get_auth_principal
    app.dependency_overrides[mcp_hub_mod.get_mcp_hub_service] = lambda: _FakeService()
    return app


@pytest.mark.asyncio
async def test_authenticated_user_can_view_hub_lists_but_cannot_mutate_without_claims() -> None:
    app = _build_app(_principal(roles=["user"], permissions=[]))
    with TestClient(app) as client:
        get_resp = client.get("/api/v1/mcp/hub/external-servers")
        post_resp = client.post(
            "/api/v1/mcp/hub/external-servers",
            json={
                "server_id": "docs",
                "name": "Docs",
                "transport": "stdio",
                "config": {"cmd": "npx"},
                "owner_scope_type": "global",
                "enabled": True,
            },
        )
    assert get_resp.status_code == 200
    assert post_resp.status_code == 403
    assert SYSTEM_CONFIGURE in post_resp.json().get("detail", "")


@pytest.mark.asyncio
async def test_authenticated_user_with_system_configure_can_mutate() -> None:
    app = _build_app(_principal(roles=["user"], permissions=[SYSTEM_CONFIGURE]))
    with TestClient(app) as client:
        post_resp = client.post(
            "/api/v1/mcp/hub/external-servers",
            json={
                "server_id": "docs",
                "name": "Docs",
                "transport": "stdio",
                "config": {"cmd": "npx"},
                "owner_scope_type": "global",
                "enabled": True,
            },
        )
    assert post_resp.status_code == 201
