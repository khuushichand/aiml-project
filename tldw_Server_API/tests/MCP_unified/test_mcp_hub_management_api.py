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

    async def get_permission_profile(self, profile_id: int) -> dict[str, Any] | None:
        return {
            "id": profile_id,
            "name": "Docs Profile",
            "owner_scope_type": "global",
            "owner_scope_id": None,
            "mode": "custom",
            "policy_document": {"capabilities": ["network.external"]},
            "is_active": True,
        }

    async def get_policy_assignment(self, assignment_id: int) -> dict[str, Any] | None:
        return {
            "id": assignment_id,
            "target_type": "persona",
            "target_id": "researcher",
            "owner_scope_type": "global",
            "owner_scope_id": None,
            "profile_id": 7,
            "inline_policy_document": {"capabilities": ["network.external"]},
            "approval_policy_id": None,
            "is_active": True,
        }

    async def list_external_servers(self, **_kwargs: Any) -> list[dict[str, Any]]:
        return [
            {
                "id": "docs",
                "name": "Docs",
                "enabled": True,
                "owner_scope_type": "global",
                "owner_scope_id": None,
                "transport": "websocket",
                "config": {"url": "wss://docs.example/ws"},
                "secret_configured": True,
                "key_hint": "cdef",
                "server_source": "managed",
                "legacy_source_ref": None,
                "superseded_by_server_id": None,
                "binding_count": 2,
                "runtime_executable": True,
                "created_by": 1,
                "updated_by": 1,
                "created_at": None,
                "updated_at": None,
            }
        ]

    async def import_legacy_external_server(self, *, server_id: str, actor_id: int | None):
        assert actor_id == 1
        assert server_id == "legacy-docs"
        return {
            "id": server_id,
            "name": "Legacy Docs",
            "enabled": True,
            "owner_scope_type": "global",
            "owner_scope_id": None,
            "transport": "websocket",
            "config": {"url": "wss://docs.example/ws"},
            "secret_configured": False,
            "key_hint": None,
            "server_source": "managed",
            "legacy_source_ref": "yaml:legacy-docs",
            "superseded_by_server_id": None,
            "binding_count": 0,
            "runtime_executable": True,
            "created_by": actor_id,
            "updated_by": actor_id,
            "created_at": None,
            "updated_at": None,
        }

    async def list_profile_credential_bindings(self, *, profile_id: int) -> list[dict[str, Any]]:
        assert profile_id == 7
        return [
            {
                "id": 1,
                "binding_target_type": "profile",
                "binding_target_id": "7",
                "external_server_id": "docs",
                "credential_ref": "server",
                "binding_mode": "grant",
                "usage_rules": {},
                "created_by": 1,
                "updated_by": 1,
                "created_at": None,
                "updated_at": None,
            }
        ]

    async def upsert_profile_credential_binding(
        self,
        *,
        profile_id: int,
        external_server_id: str,
        actor_id: int | None,
    ) -> dict[str, Any]:
        assert profile_id == 7
        assert external_server_id == "docs"
        assert actor_id == 1
        return {
            "id": 1,
            "binding_target_type": "profile",
            "binding_target_id": "7",
            "external_server_id": "docs",
            "credential_ref": "server",
            "binding_mode": "grant",
            "usage_rules": {},
            "created_by": 1,
            "updated_by": 1,
            "created_at": None,
            "updated_at": None,
        }

    async def delete_profile_credential_binding(
        self,
        *,
        profile_id: int,
        external_server_id: str,
        actor_id: int | None,
    ) -> bool:
        assert profile_id == 7
        assert external_server_id == "docs"
        assert actor_id == 1
        return True

    async def list_assignment_credential_bindings(self, *, assignment_id: int) -> list[dict[str, Any]]:
        assert assignment_id == 11
        return [
            {
                "id": 2,
                "binding_target_type": "assignment",
                "binding_target_id": "11",
                "external_server_id": "docs",
                "credential_ref": "server",
                "binding_mode": "disable",
                "usage_rules": {},
                "created_by": 1,
                "updated_by": 1,
                "created_at": None,
                "updated_at": None,
            }
        ]

    async def upsert_assignment_credential_binding(
        self,
        *,
        assignment_id: int,
        external_server_id: str,
        binding_mode: str,
        actor_id: int | None,
    ) -> dict[str, Any]:
        assert assignment_id == 11
        assert external_server_id == "docs"
        assert binding_mode == "disable"
        assert actor_id == 1
        return {
            "id": 2,
            "binding_target_type": "assignment",
            "binding_target_id": "11",
            "external_server_id": "docs",
            "credential_ref": "server",
            "binding_mode": "disable",
            "usage_rules": {},
            "created_by": 1,
            "updated_by": 1,
            "created_at": None,
            "updated_at": None,
        }

    async def delete_assignment_credential_binding(
        self,
        *,
        assignment_id: int,
        external_server_id: str,
        actor_id: int | None,
    ) -> bool:
        assert assignment_id == 11
        assert external_server_id == "docs"
        assert actor_id == 1
        return True

    async def resolve_effective_external_access(
        self,
        *,
        assignment_id: int,
        actor_id: int | None,
    ) -> dict[str, Any]:
        assert assignment_id == 11
        assert actor_id == 1
        return {
            "servers": [
                {
                    "server_id": "docs",
                    "server_name": "Docs",
                    "granted_by": "profile",
                    "disabled_by_assignment": True,
                    "server_source": "managed",
                    "superseded_by_server_id": None,
                    "secret_available": True,
                    "runtime_executable": False,
                    "blocked_reason": "disabled_by_assignment",
                }
            ]
        }

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


@pytest.mark.asyncio
async def test_list_external_servers_includes_source_state_fields() -> None:
    app = _build_app(
        principal=_make_principal(roles=["admin"], permissions=[]),
        fail_with_401=False,
    )
    with TestClient(app) as client:
        resp = client.get("/api/v1/mcp/hub/external-servers")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload[0]["server_source"] == "managed"
    assert payload[0]["binding_count"] == 2
    assert payload[0]["runtime_executable"] is True


@pytest.mark.asyncio
async def test_import_legacy_external_server_endpoint_returns_managed_row() -> None:
    app = _build_app(
        principal=_make_principal(roles=["admin"], permissions=[]),
        fail_with_401=False,
    )
    with TestClient(app) as client:
        resp = client.post("/api/v1/mcp/hub/external-servers/legacy-docs/import")

    assert resp.status_code == 201
    payload = resp.json()
    assert payload["id"] == "legacy-docs"
    assert payload["server_source"] == "managed"
    assert payload["legacy_source_ref"] == "yaml:legacy-docs"


@pytest.mark.asyncio
async def test_profile_credential_binding_endpoints_round_trip() -> None:
    app = _build_app(
        principal=_make_principal(roles=["admin"], permissions=[]),
        fail_with_401=False,
    )
    with TestClient(app) as client:
        list_resp = client.get("/api/v1/mcp/hub/permission-profiles/7/credential-bindings")
        put_resp = client.put("/api/v1/mcp/hub/permission-profiles/7/credential-bindings/docs")
        delete_resp = client.delete("/api/v1/mcp/hub/permission-profiles/7/credential-bindings/docs")

    assert list_resp.status_code == 200
    assert list_resp.json()[0]["binding_mode"] == "grant"
    assert put_resp.status_code == 200
    assert put_resp.json()["external_server_id"] == "docs"
    assert delete_resp.status_code == 200
    assert delete_resp.json()["ok"] is True


@pytest.mark.asyncio
async def test_assignment_credential_binding_and_external_access_endpoints_round_trip() -> None:
    app = _build_app(
        principal=_make_principal(roles=["admin"], permissions=[]),
        fail_with_401=False,
    )
    with TestClient(app) as client:
        list_resp = client.get("/api/v1/mcp/hub/policy-assignments/11/credential-bindings")
        put_resp = client.put(
            "/api/v1/mcp/hub/policy-assignments/11/credential-bindings/docs",
            json={"binding_mode": "disable"},
        )
        preview_resp = client.get("/api/v1/mcp/hub/policy-assignments/11/external-access")

    assert list_resp.status_code == 200
    assert list_resp.json()[0]["binding_mode"] == "disable"
    assert put_resp.status_code == 200
    assert put_resp.json()["binding_mode"] == "disable"
    assert preview_resp.status_code == 200
    assert preview_resp.json()["servers"][0]["blocked_reason"] == "disabled_by_assignment"
