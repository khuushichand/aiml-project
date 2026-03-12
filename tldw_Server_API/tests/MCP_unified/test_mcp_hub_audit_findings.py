from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from tldw_Server_API.app.api.v1.API_Deps import auth_deps
from tldw_Server_API.app.api.v1.endpoints import mcp_hub_management
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.services.mcp_hub_service import McpHubService


class _Repo:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.workspace_sets = [
            {
                "id": 51,
                "name": "Primary Workspace Set",
                "owner_scope_type": "user",
                "owner_scope_id": 7,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }
        ]
        self.workspace_set_members = {
            51: [
                {"workspace_set_object_id": 51, "workspace_id": "workspace-alpha"},
                {"workspace_set_object_id": 51, "workspace_id": "workspace-beta"},
            ]
        }
        self.shared_entries = [
            {
                "id": 71,
                "workspace_id": "shared-docs",
                "display_name": "Shared Docs",
                "absolute_root": "/srv/shared/docs",
                "owner_scope_type": "team",
                "owner_scope_id": 21,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": 72,
                "workspace_id": "shared-docs-archive",
                "display_name": "Shared Docs Archive",
                "absolute_root": "/srv/shared/docs/archive",
                "owner_scope_type": "team",
                "owner_scope_id": 21,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            },
        ]
        self.assignments = [
            {
                "id": 11,
                "target_type": "persona",
                "target_id": "researcher",
                "owner_scope_type": "user",
                "owner_scope_id": 7,
                "profile_id": None,
                "path_scope_object_id": None,
                "workspace_source_mode": "named",
                "workspace_set_object_id": 51,
                "inline_policy_document": {"path_scope_mode": "workspace_root"},
                "approval_policy_id": None,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }
        ]
        self.external_servers = [
            {
                "id": "docs-managed",
                "name": "Docs Managed",
                "enabled": True,
                "owner_scope_type": "global",
                "owner_scope_id": None,
                "transport": "stdio",
                "config": {},
                "secret_configured": False,
                "server_source": "managed",
                "binding_count": 1,
                "runtime_executable": False,
                "auth_template_present": True,
                "auth_template_valid": False,
                "auth_template_blocked_reason": "required_slot_secret_missing",
                "created_at": now,
                "updated_at": now,
            }
        ]
        self.assignment_bindings = {
            11: [
                {
                    "id": 91,
                    "binding_target_type": "policy_assignment",
                    "binding_target_id": "11",
                    "external_server_id": "docs-managed",
                    "slot_name": "token_readonly",
                    "credential_ref": "slot",
                    "binding_mode": "grant",
                    "usage_rules": {},
                    "created_at": now,
                    "updated_at": now,
                }
            ]
        }

    async def list_workspace_set_objects(
        self,
        *,
        owner_scope_type: str | None = None,
        owner_scope_id: int | None = None,
    ):
        rows = list(self.workspace_sets)
        if owner_scope_type is not None:
            rows = [row for row in rows if row["owner_scope_type"] == owner_scope_type]
        if owner_scope_id is not None:
            rows = [row for row in rows if row["owner_scope_id"] == owner_scope_id]
        return rows

    async def get_workspace_set_object(self, workspace_set_object_id: int):
        for row in self.workspace_sets:
            if int(row["id"]) == int(workspace_set_object_id):
                return dict(row)
        return None

    async def list_workspace_set_members(self, workspace_set_object_id: int):
        return list(self.workspace_set_members.get(int(workspace_set_object_id), []))

    async def list_shared_workspace_entries(
        self,
        *,
        owner_scope_type: str | None = None,
        owner_scope_id: int | None = None,
        workspace_id: str | None = None,
    ):
        rows = list(self.shared_entries)
        if workspace_id is not None:
            rows = [row for row in rows if row["workspace_id"] == workspace_id]
        if owner_scope_type is not None:
            rows = [row for row in rows if row["owner_scope_type"] == owner_scope_type]
        if owner_scope_type != "global" and owner_scope_id is not None:
            rows = [row for row in rows if row["owner_scope_id"] == owner_scope_id]
        return rows

    async def get_shared_workspace_entry(self, shared_workspace_id: int):
        for row in self.shared_entries:
            if int(row["id"]) == int(shared_workspace_id):
                return dict(row)
        return None

    async def list_policy_assignments(
        self,
        *,
        owner_scope_type: str | None = None,
        owner_scope_id: int | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        active_only: bool = True,
    ):
        _ = active_only
        rows = list(self.assignments)
        if owner_scope_type is not None:
            rows = [row for row in rows if row["owner_scope_type"] == owner_scope_type]
        if owner_scope_id is not None:
            rows = [row for row in rows if row["owner_scope_id"] == owner_scope_id]
        if target_type is not None:
            rows = [row for row in rows if row["target_type"] == target_type]
        if target_id is not None:
            rows = [row for row in rows if row["target_id"] == target_id]
        return rows

    async def get_permission_profile(self, profile_id: int):
        _ = profile_id
        return None

    async def get_path_scope_object(self, path_scope_object_id: int):
        _ = path_scope_object_id
        return None

    async def get_policy_override_by_assignment(self, assignment_id: int):
        _ = assignment_id
        return None

    async def list_policy_assignment_workspaces(self, assignment_id: int):
        _ = assignment_id
        return []

    async def list_external_servers(
        self,
        *,
        owner_scope_type: str | None = None,
        owner_scope_id: int | None = None,
        server_source: str | None = None,
    ):
        rows = list(self.external_servers)
        if owner_scope_type is not None:
            rows = [row for row in rows if row["owner_scope_type"] == owner_scope_type]
        if owner_scope_id is not None:
            rows = [row for row in rows if row["owner_scope_id"] == owner_scope_id]
        if server_source is not None:
            rows = [row for row in rows if row["server_source"] == server_source]
        return rows

    async def list_external_server_credential_slots(self, server_id: str):
        _ = server_id
        return [
            {
                "server_id": "docs-managed",
                "slot_name": "token_readonly",
                "display_name": "Read-only token",
                "secret_kind": "bearer_token",
                "privilege_class": "read",
                "is_required": True,
                "secret_configured": False,
            }
        ]

    async def list_assignment_credential_bindings(self, assignment_id: int):
        return list(self.assignment_bindings.get(int(assignment_id), []))


class _Resolver:
    async def resolve_for_context(
        self,
        *,
        session_id: str | None,
        user_id: str | None,
        workspace_id: str | None,
        workspace_trust_source: str | None = None,
        owner_scope_type: str | None = None,
        owner_scope_id: int | None = None,
    ):
        _ = session_id
        _ = user_id
        _ = owner_scope_type
        _ = owner_scope_id
        mapping = {
            "workspace-alpha": "/repo",
            "workspace-beta": "/repo/docs",
            "shared-docs": "/srv/shared/docs",
            "shared-docs-archive": "/srv/shared/docs/archive",
        }
        root = mapping.get(str(workspace_id or "").strip())
        return {
            "workspace_root": root,
            "workspace_id": workspace_id,
            "source": workspace_trust_source or "user_local",
            "reason": None if root else "workspace_root_unavailable",
        }


class _ExternalAccessResolver:
    async def resolve_assignment_external_access(
        self,
        *,
        assignment_id: int,
        owner_scope_type: str,
        owner_scope_id: int | None,
        profile_id: int | None,
    ):
        _ = owner_scope_type
        _ = owner_scope_id
        _ = profile_id
        if int(assignment_id) != 11:
            return {"servers": []}
        return {
            "servers": [
                {
                    "server_id": "docs-managed",
                    "server_name": "Docs Managed",
                    "granted_by": "assignment",
                    "disabled_by_assignment": False,
                    "server_source": "managed",
                    "secret_available": False,
                    "runtime_executable": False,
                    "blocked_reason": "required_slot_not_granted",
                    "requested_slots": ["token_readonly"],
                    "bound_slots": [],
                    "missing_bound_slots": ["token_readonly"],
                    "missing_secret_slots": [],
                    "slots": [
                        {
                            "slot_name": "token_readonly",
                            "display_name": "Read-only token",
                            "granted_by": "assignment",
                            "disabled_by_assignment": False,
                            "secret_available": False,
                            "runtime_usable": False,
                            "blocked_reason": "required_slot_not_granted",
                        }
                    ],
                }
            ]
        }


def _make_principal() -> AuthPrincipal:
    return AuthPrincipal(
        kind="user",
        user_id=7,
        api_key_id=None,
        subject="7",
        token_type="access",
        jti=None,
        roles=["admin"],
        permissions=["system.configure"],
        is_admin=False,
        org_ids=[],
        team_ids=[21],
    )


@pytest.mark.asyncio
async def test_list_governance_audit_findings_returns_workspace_and_external_findings():
    service = McpHubService(repo=_Repo())
    service.workspace_root_resolver = _Resolver()
    service.external_access_resolver = _ExternalAccessResolver()

    findings = await service.list_governance_audit_findings(actor_id=7)

    finding_types = {finding["finding_type"] for finding in findings["items"]}
    assert "workspace_source_readiness_warning" in finding_types
    assert "shared_workspace_overlap_warning" in finding_types
    assert "assignment_validation_blocker" in finding_types
    assert "external_server_configuration_issue" in finding_types
    assert "external_binding_issue" in finding_types


def test_audit_findings_endpoint_returns_normalized_payload():
    service = McpHubService(repo=_Repo())
    service.workspace_root_resolver = _Resolver()
    service.external_access_resolver = _ExternalAccessResolver()

    app = FastAPI()
    app.include_router(mcp_hub_management.router, prefix="/api/v1")
    app.dependency_overrides[mcp_hub_management.get_mcp_hub_service] = lambda: service
    app.dependency_overrides[auth_deps.get_auth_principal] = _make_principal

    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/mcp/hub/audit/findings")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 4
    assert payload["counts"]["error"] >= 1
    assert payload["counts"]["warning"] >= 1
    finding_types = {item["finding_type"] for item in payload["items"]}
    assert "assignment_validation_blocker" in finding_types
    assert "workspace_source_readiness_warning" in finding_types
