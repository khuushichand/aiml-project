from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest
from starlette.requests import Request

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.api.v1.endpoints import mcp_hub_management
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.exceptions import BadRequestError, ResourceNotFoundError


def _make_principal(
    *,
    roles: list[str] | None = None,
    permissions: list[str] | None = None,
) -> AuthPrincipal:
    return AuthPrincipal(
        kind="user",
        user_id=1,
        api_key_id=None,
        subject="1",
        token_type="access",
        jti=None,
        roles=roles or [],
        permissions=permissions or [],
        is_admin=False,
        org_ids=[],
        team_ids=[],
    )


class _FakeService:
    async def list_acp_profiles(self, **_kwargs: Any) -> list[dict[str, Any]]:
        return []

    async def set_external_server_secret(self, *, server_id: str, secret_value: str, actor_id: int | None):
        assert actor_id == 1
        assert server_id == "docs"
        assert secret_value == "abc123secret"
        return {
            "server_id": server_id,
            "secret_configured": True,
            "key_hint": "cdef",
            "updated_at": None,
        }


def _build_app(
    *,
    principal: AuthPrincipal | None,
    fail_with_401: bool,
) -> FastAPI:
    app = FastAPI()
    app.include_router(mcp_hub_management.router, prefix="/api/v1")

    async def _fake_get_auth_principal(_request: Request) -> AuthPrincipal:  # type: ignore[override]
        if fail_with_401:
            raise HTTPException(
                status_code=401,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        assert principal is not None
        return principal

    app.dependency_overrides[auth_deps.get_auth_principal] = _fake_get_auth_principal
    app.dependency_overrides[mcp_hub_management.get_mcp_hub_service] = lambda: _FakeService()
    return app


@pytest.mark.asyncio
async def test_get_mcp_hub_profiles_requires_auth() -> None:
    app = _build_app(principal=None, fail_with_401=True)
    with TestClient(app) as client:
        resp = client.get("/api/v1/mcp/hub/acp-profiles")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_set_external_secret_returns_masked_only() -> None:
    app = _build_app(
        principal=_make_principal(roles=["admin"], permissions=[]),
        fail_with_401=False,
    )
    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/mcp/hub/external-servers/docs/secret",
            json={"secret": "abc123secret"},
        )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["secret_configured"] is True
    assert "abc123secret" not in json.dumps(payload)


@pytest.mark.asyncio
async def test_set_external_secret_not_found_maps_to_404() -> None:
    class _MissingService(_FakeService):
        async def set_external_server_secret(self, *, server_id: str, secret_value: str, actor_id: int | None):
            raise ResourceNotFoundError("mcp_external_server", identifier=server_id)

    app = _build_app(
        principal=_make_principal(roles=["admin"], permissions=[]),
        fail_with_401=False,
    )
    app.dependency_overrides[mcp_hub_management.get_mcp_hub_service] = lambda: _MissingService()
    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/mcp/hub/external-servers/docs/secret",
            json={"secret": "abc123secret"},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_set_external_secret_bad_request_maps_to_400() -> None:
    class _BadPayloadService(_FakeService):
        async def set_external_server_secret(self, *, server_id: str, secret_value: str, actor_id: int | None):
            raise BadRequestError("Secret value is required")

    app = _build_app(
        principal=_make_principal(roles=["admin"], permissions=[]),
        fail_with_401=False,
    )
    app.dependency_overrides[mcp_hub_management.get_mcp_hub_service] = lambda: _BadPayloadService()
    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/mcp/hub/external-servers/docs/secret",
            json={"secret": "abc123secret"},
        )
    assert resp.status_code == 400
