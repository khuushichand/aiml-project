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
from tldw_Server_API.app.services.mcp_hub_service import McpHubConflictError


class _FakeService:
    def __init__(self) -> None:
        self.acp_calls: list[dict[str, Any]] = []
        self.external_calls: list[dict[str, Any]] = []

    async def list_acp_profiles(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.acp_calls.append(kwargs)
        return []

    async def list_external_servers(self, **_kwargs: Any) -> list[dict[str, Any]]:
        self.external_calls.append(dict(_kwargs))
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


def _build_app(principal: AuthPrincipal) -> tuple[FastAPI, _FakeService]:
    app = FastAPI()
    app.include_router(mcp_hub_mod.router, prefix="/api/v1")
    fake_service = _FakeService()

    async def _fake_get_auth_principal(_request: Request) -> AuthPrincipal:  # type: ignore[override]
        return principal

    app.dependency_overrides[auth_deps.get_auth_principal] = _fake_get_auth_principal
    app.dependency_overrides[mcp_hub_mod.get_mcp_hub_service] = lambda: fake_service
    return app, fake_service


@pytest.mark.asyncio
async def test_authenticated_user_can_view_hub_lists_but_cannot_mutate_without_claims() -> None:
    app, _ = _build_app(_principal(roles=["user"], permissions=[]))
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
    app, _ = _build_app(_principal(roles=["user"], permissions=[SYSTEM_CONFIGURE]))
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


@pytest.mark.asyncio
async def test_non_admin_default_list_queries_are_scope_bounded() -> None:
    principal = _principal(roles=["user"], permissions=[])
    principal.org_ids = [7]
    principal.team_ids = [9]
    app, svc = _build_app(principal)

    with TestClient(app) as client:
        acp_resp = client.get("/api/v1/mcp/hub/acp-profiles")
        ext_resp = client.get("/api/v1/mcp/hub/external-servers")

    assert acp_resp.status_code == 200
    assert ext_resp.status_code == 200

    assert {"owner_scope_type": "global", "owner_scope_id": None} in svc.acp_calls
    assert {"owner_scope_type": "user", "owner_scope_id": 1} in svc.acp_calls
    assert {"owner_scope_type": "org", "owner_scope_id": 7} in svc.acp_calls
    assert {"owner_scope_type": "team", "owner_scope_id": 9} in svc.acp_calls

    assert {"owner_scope_type": "global", "owner_scope_id": None} in svc.external_calls
    assert {"owner_scope_type": "user", "owner_scope_id": 1} in svc.external_calls
    assert {"owner_scope_type": "org", "owner_scope_id": 7} in svc.external_calls
    assert {"owner_scope_type": "team", "owner_scope_id": 9} in svc.external_calls


@pytest.mark.asyncio
async def test_non_admin_cannot_query_other_scope_ids() -> None:
    principal = _principal(roles=["user"], permissions=[])
    principal.org_ids = [7]
    app, _ = _build_app(principal)

    with TestClient(app) as client:
        forbidden = client.get("/api/v1/mcp/hub/external-servers?owner_scope_type=org&owner_scope_id=999")
        denied_user = client.get("/api/v1/mcp/hub/acp-profiles?owner_scope_type=user&owner_scope_id=2")

    assert forbidden.status_code == 403
    assert denied_user.status_code == 403


@pytest.mark.asyncio
async def test_create_external_server_conflict_maps_to_409() -> None:
    class _ConflictService(_FakeService):
        async def create_external_server(self, **_kwargs: Any) -> dict[str, Any]:
            raise McpHubConflictError("External server already exists: docs")

    app = FastAPI()
    app.include_router(mcp_hub_mod.router, prefix="/api/v1")

    async def _fake_get_auth_principal(_request: Request) -> AuthPrincipal:  # type: ignore[override]
        return _principal(roles=["user"], permissions=[SYSTEM_CONFIGURE])

    app.dependency_overrides[auth_deps.get_auth_principal] = _fake_get_auth_principal
    app.dependency_overrides[mcp_hub_mod.get_mcp_hub_service] = lambda: _ConflictService()

    with TestClient(app) as client:
        resp = client.post(
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

    assert resp.status_code == 409
