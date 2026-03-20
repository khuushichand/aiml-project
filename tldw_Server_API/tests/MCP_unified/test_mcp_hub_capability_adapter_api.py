from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from starlette.requests import Request

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.api.v1.endpoints import mcp_hub_management
from tldw_Server_API.app.core.AuthNZ.permissions import SYSTEM_CONFIGURE
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.exceptions import BadRequestError


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


class _FakeCapabilityAdapterService:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.preview_calls: list[dict] = []
        self.create_calls: list[dict] = []
        self.update_calls: list[dict] = []
        self.delete_calls: list[int] = []
        self.preview_error: Exception | None = None
        self.inventory = [
            {
                "id": 11,
                "mapping_id": "research.global",
                "title": "Research",
                "description": "Global research mapping",
                "owner_scope_type": "global",
                "owner_scope_id": None,
                "capability_name": "tool.invoke.research",
                "adapter_contract_version": 1,
                "resolved_policy_document": {"allowed_tools": ["web.search"]},
                "supported_environment_requirements": ["workspace_bounded_read"],
                "is_active": True,
                "created_by": 7,
                "updated_by": 7,
                "created_at": now,
                "updated_at": now,
            }
        ]

    async def preview_mapping(self, **kwargs):
        self.preview_calls.append(dict(kwargs))
        if self.preview_error is not None:
            raise self.preview_error
        scope_type = kwargs["owner_scope_type"]
        scope_id = kwargs.get("owner_scope_id")
        display_scope = scope_type if scope_id is None else f"{scope_type}:{scope_id}"
        return {
            "normalized_mapping": {
                "mapping_id": kwargs["mapping_id"],
                "title": kwargs.get("title") or kwargs["mapping_id"],
                "description": kwargs.get("description"),
                "owner_scope_type": scope_type,
                "owner_scope_id": scope_id,
                "capability_name": kwargs["capability_name"],
                "adapter_contract_version": kwargs["adapter_contract_version"],
                "resolved_policy_document": dict(kwargs["resolved_policy_document"]),
                "supported_environment_requirements": list(kwargs["supported_environment_requirements"]),
                "is_active": kwargs.get("is_active", True),
            },
            "warnings": ["preview warning"] if kwargs["supported_environment_requirements"] else [],
            "affected_scope_summary": {
                "owner_scope_type": scope_type,
                "owner_scope_id": scope_id,
                "display_scope": display_scope,
            },
        }

    async def preview_update(self, capability_adapter_mapping_id: int, **kwargs):
        if int(capability_adapter_mapping_id) != 11:
            raise BadRequestError("missing mapping")
        current = dict(self.inventory[0])
        current.update({key: value for key, value in kwargs.items() if value is not None})
        return await self.preview_mapping(**current)

    async def create_mapping(self, **kwargs):
        self.create_calls.append(dict(kwargs))
        row = dict(self.inventory[0])
        row.update(
            {
                "mapping_id": kwargs["mapping_id"],
                "title": kwargs.get("title") or kwargs["mapping_id"],
                "description": kwargs.get("description"),
                "owner_scope_type": kwargs["owner_scope_type"],
                "owner_scope_id": kwargs.get("owner_scope_id"),
                "capability_name": kwargs["capability_name"],
                "adapter_contract_version": kwargs["adapter_contract_version"],
                "resolved_policy_document": dict(kwargs["resolved_policy_document"]),
                "supported_environment_requirements": list(kwargs["supported_environment_requirements"]),
                "is_active": kwargs.get("is_active", True),
                "updated_by": kwargs.get("actor_id"),
            }
        )
        self.inventory = [row]
        return row

    async def list_capability_adapter_mappings(self, **_kwargs):
        return list(self.inventory)

    async def update_mapping(self, capability_adapter_mapping_id: int, **kwargs):
        self.update_calls.append({"id": capability_adapter_mapping_id, **dict(kwargs)})
        if int(capability_adapter_mapping_id) != 11:
            return None
        row = dict(self.inventory[0])
        row.update(
            {
                "title": kwargs.get("title") or row["title"],
                "description": kwargs.get("description", row["description"]),
                "resolved_policy_document": dict(kwargs.get("resolved_policy_document") or row["resolved_policy_document"]),
                "supported_environment_requirements": list(
                    kwargs.get("supported_environment_requirements") or row["supported_environment_requirements"]
                ),
                "updated_by": kwargs.get("actor_id"),
            }
        )
        self.inventory = [row]
        return row

    async def delete_capability_adapter_mapping(self, capability_adapter_mapping_id: int):
        self.delete_calls.append(int(capability_adapter_mapping_id))
        return int(capability_adapter_mapping_id) == 11


def _build_app(
    principal: AuthPrincipal,
    *,
    capability_adapter_service: _FakeCapabilityAdapterService | None = None,
) -> FastAPI:
    app = FastAPI()
    app.include_router(mcp_hub_management.router, prefix="/api/v1")

    async def _fake_get_auth_principal(_request: Request) -> AuthPrincipal:  # type: ignore[override]
        return principal

    app.dependency_overrides[auth_deps.get_auth_principal] = _fake_get_auth_principal
    app.dependency_overrides[mcp_hub_management.get_mcp_hub_capability_adapter_service] = (
        lambda: capability_adapter_service or _FakeCapabilityAdapterService()
    )
    return app


def _mapping_payload() -> dict:
    return {
        "mapping_id": "research.global",
        "title": "Research",
        "description": "Global research mapping",
        "owner_scope_type": "global",
        "owner_scope_id": None,
        "capability_name": "tool.invoke.research",
        "adapter_contract_version": 1,
        "resolved_policy_document": {"allowed_tools": ["web.search"]},
        "supported_environment_requirements": ["workspace_bounded_read"],
        "is_active": True,
    }


def test_capability_mapping_preview_returns_normalized_report() -> None:
    service = _FakeCapabilityAdapterService()
    app = _build_app(
        _make_principal(permissions=[SYSTEM_CONFIGURE, "grant.tool.invoke"]),
        capability_adapter_service=service,
    )

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/mcp/hub/capability-mappings/preview",
            json=_mapping_payload(),
        )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["normalized_mapping"]["resolved_policy_document"] == {
        "allowed_tools": ["web.search"]
    }
    assert payload["affected_scope_summary"]["display_scope"] == "global"
    assert service.preview_calls


def test_capability_mapping_create_requires_grant_authority() -> None:
    service = _FakeCapabilityAdapterService()
    app = _build_app(
        _make_principal(permissions=[SYSTEM_CONFIGURE]),
        capability_adapter_service=service,
    )

    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/mcp/hub/capability-mappings",
            json=_mapping_payload(),
        )

    assert resp.status_code == 403
    assert "grant.tool.invoke" in resp.json()["detail"]
    assert service.create_calls == []


def test_capability_mapping_crud_round_trip() -> None:
    service = _FakeCapabilityAdapterService()
    app = _build_app(
        _make_principal(permissions=[SYSTEM_CONFIGURE, "grant.tool.invoke"]),
        capability_adapter_service=service,
    )

    with TestClient(app) as client:
        list_resp = client.get("/api/v1/mcp/hub/capability-mappings")
        create_resp = client.post(
            "/api/v1/mcp/hub/capability-mappings",
            json=_mapping_payload(),
        )
        update_resp = client.put(
            "/api/v1/mcp/hub/capability-mappings/11",
            json={
                "title": "Research Updated",
                "resolved_policy_document": {"allowed_tools": ["docs.search"]},
                "supported_environment_requirements": ["workspace_bounded_read"],
            },
        )
        delete_resp = client.delete("/api/v1/mcp/hub/capability-mappings/11")

    assert list_resp.status_code == 200
    assert list_resp.json()[0]["mapping_id"] == "research.global"
    assert create_resp.status_code == 201
    assert create_resp.json()["mapping_id"] == "research.global"
    assert update_resp.status_code == 200
    assert update_resp.json()["title"] == "Research Updated"
    assert delete_resp.status_code == 200
    assert delete_resp.json() == {"ok": True}


def test_capability_mapping_create_returns_bad_request_for_invalid_contract_version() -> None:
    service = _FakeCapabilityAdapterService()
    service.preview_error = BadRequestError("adapter_contract_version must be 1")
    app = _build_app(
        _make_principal(permissions=[SYSTEM_CONFIGURE, "grant.tool.invoke"]),
        capability_adapter_service=service,
    )

    payload = _mapping_payload()
    payload["adapter_contract_version"] = 2

    with TestClient(app) as client:
        resp = client.post("/api/v1/mcp/hub/capability-mappings", json=payload)

    assert resp.status_code == 400
    assert resp.json()["detail"] == "adapter_contract_version must be 1"
    assert service.create_calls == []
