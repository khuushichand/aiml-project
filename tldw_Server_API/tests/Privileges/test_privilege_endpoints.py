import asyncio
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app as fastapi_app
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_current_active_user
from tldw_Server_API.app.core.PrivilegeMaps.service import PrivilegeMapService
from tldw_Server_API.app.core.PrivilegeMaps.snapshots import PrivilegeSnapshotStore, get_privilege_snapshot_store
from tldw_Server_API.app.core.PrivilegeMaps.service import get_privilege_map_service


class FakePrivilegeMapService(PrivilegeMapService):
    def __init__(self) -> None:
        super().__init__()
        self.sample_users = [
            {
                "id": "user-1",
                "username": "Alex Rivera",
                "primary_role": "admin",
                "roles": ["admin"],
                "permissions": [],
                "feature_flags": {flag.id for flag in self.catalog.feature_flags},
                "allowed_scopes": {scope.id for scope in self.catalog.scopes},
            },
            {
                "id": "user-2",
                "username": "Priya Patel",
                "primary_role": "analyst",
                "roles": ["analyst"],
                "permissions": {"rag.search"},
                "feature_flags": {"media_ingest_beta"},
                "allowed_scopes": {"rag.search"},
            },
            {
                "id": "user-3",
                "username": "Morgan Lee",
                "primary_role": "viewer",
                "roles": ["viewer"],
                "permissions": {"media.catalog.view"},
                "feature_flags": set(),
                "allowed_scopes": {"media.catalog.view"},
            },
        ]
        self.sample_memberships = [
            {"team_id": "team-1", "user_id": "user-1", "team_name": "Core Admins", "org_id": "acme"},
            {"team_id": "team-1", "user_id": "user-2", "team_name": "Core Admins", "org_id": "acme"},
            {"team_id": "team-2", "user_id": "user-3", "team_name": "Viewers", "org_id": "acme"},
        ]

    async def _fetch_users(self):
        return list(self.sample_users)

    async def _fetch_team_memberships(self):
        return list(self.sample_memberships)


@pytest.fixture()
def privilege_test_client():
    fake_service = FakePrivilegeMapService()
    snapshot_store = PrivilegeSnapshotStore()

    async def seed_snapshots():
        await snapshot_store.clear()
        await snapshot_store.add_snapshot(
            {
                "snapshot_id": "snap-2025-01-15-001",
                "generated_at": datetime(2025, 1, 15, 10, 0, tzinfo=timezone.utc).isoformat(),
                "generated_by": "user-42",
                "target_scope": "org",
                "org_id": "acme",
                "team_id": None,
                "catalog_version": fake_service.catalog.version,
                "summary": {
                    "users": 2,
                    "scopes": 3,
                    "endpoints": 3,
                    "scope_ids": ["media.ingest", "chat.admin", "rag.search"],
                    "sensitivity_breakdown": {"high": 1, "restricted": 1, "moderate": 1},
                },
            }
        )
        await snapshot_store.add_snapshot(
            {
                "snapshot_id": "snap-2025-01-12-001",
                "generated_at": datetime(2025, 1, 12, 12, 30, tzinfo=timezone.utc).isoformat(),
                "generated_by": "user-99",
                "target_scope": "team",
                "org_id": "beta",
                "team_id": "team-2",
                "catalog_version": fake_service.catalog.version,
                "summary": {
                    "users": 1,
                    "scopes": 1,
                    "endpoints": 1,
                    "scope_ids": ["media.catalog.view"],
                    "sensitivity_breakdown": {"low": 1},
                },
            }
        )

    asyncio.run(seed_snapshots())

    def override_current_user():
        return {"id": "admin-1", "username": "Admin User", "role": "admin", "is_admin": True}

    fastapi_app.dependency_overrides[get_current_active_user] = override_current_user
    fastapi_app.dependency_overrides[get_privilege_map_service] = lambda: fake_service
    fastapi_app.dependency_overrides[get_privilege_snapshot_store] = lambda: snapshot_store

    with TestClient(fastapi_app) as client:
        yield client

    asyncio.run(snapshot_store.clear())
    fastapi_app.dependency_overrides.clear()


def test_get_org_summary_group_by_role(privilege_test_client: TestClient):
    response = privilege_test_client.get("/api/v1/privileges/org")
    assert response.status_code == 200
    payload = response.json()
    assert payload["group_by"] == "role"
    assert "trends" in payload
    assert isinstance(payload["trends"], list)
    keys = {bucket["key"] for bucket in payload["buckets"]}
    assert "admin" in keys
    assert "analyst" in keys


def test_get_org_detail_pagination(privilege_test_client: TestClient):
    response = privilege_test_client.get(
        "/api/v1/privileges/org",
        params={"view": "detail", "page": 1, "page_size": 5},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 1
    assert payload["page_size"] == 5
    assert payload["items"], "Expected detail items to be present"
    statuses = {item["status"] for item in payload["items"]}
    assert statuses.issubset({"allowed", "blocked"})


def test_team_detail_filters(privilege_test_client: TestClient):
    response = privilege_test_client.get(
        "/api/v1/privileges/teams/team-1",
        params={"view": "detail", "page": 1, "page_size": 5, "resource": "media"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_items"] >= 1
    for item in payload["items"]:
        assert "media" in item["endpoint"]


def test_snapshot_list_filters(privilege_test_client: TestClient):
    response = privilege_test_client.get(
        "/api/v1/privileges/snapshots",
        params={"org_id": "acme", "include_counts": True},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_items"] == 1
    assert payload["items"][0]["org_id"] == "acme"
    assert payload["items"][0]["target_scope"] == "org"

    response = privilege_test_client.get(
        "/api/v1/privileges/snapshots",
        params={"scope": "media.catalog.view"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_items"] == 1
    assert payload["items"][0]["snapshot_id"] == "snap-2025-01-12-001"


def test_get_self_map(privilege_test_client: TestClient):
    response = privilege_test_client.get("/api/v1/privileges/self")
    assert response.status_code == 200
    payload = response.json()
    assert "items" in payload
    assert "recommended_actions" in payload


def test_get_snapshot_detail(privilege_test_client: TestClient):
    response = privilege_test_client.get("/api/v1/privileges/snapshots/snap-2025-01-15-001")
    assert response.status_code == 200
    payload = response.json()
    assert payload["snapshot_id"] == "snap-2025-01-15-001"
    assert payload["detail"]["items"] == []
    assert payload["target_scope"] == "org"


def test_create_snapshot_org(privilege_test_client: TestClient):
    response = privilege_test_client.post(
        "/api/v1/privileges/snapshots",
        json={
            "target_scope": "org",
            "org_id": "acme",
            "notes": "automation-test",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["target_scope"] == "org"
    assert payload["summary"]["users"] >= 1
