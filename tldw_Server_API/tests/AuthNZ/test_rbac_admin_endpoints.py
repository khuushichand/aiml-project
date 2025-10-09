import os
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


def _client():
    # Ensure single-user default auth path works
    # Deterministic key is provided by settings when none is set
    headers = {"X-API-KEY": os.getenv("SINGLE_USER_API_KEY", "test-api-key-12345")}
    return TestClient(app, headers=headers)


def test_list_roles_contains_seeded_roles():
    with _client() as client:
        r = client.get("/api/v1/admin/roles")
        assert r.status_code == 200, r.text
        roles = r.json()
        names = {role["name"] for role in roles}
        # Seeded by migration_014
        assert {"admin", "user", "moderator"}.issubset(names)


def test_create_permission_and_assign_to_role():
    with _client() as client:
        # Create a new permission
        perm_code = "qa.run_checks"
        pr = client.post("/api/v1/admin/permissions", json={"name": perm_code, "category": "qa"})
        assert pr.status_code == 200, pr.text
        perm = pr.json()
        perm_id = perm["id"]

        # Create a role
        rr = client.post("/api/v1/admin/roles", json={"name": "qa", "description": "QA role"})
        assert rr.status_code == 200, rr.text
        role = rr.json()
        role_id = role["id"]

        # Grant permission to role
        gr = client.post(f"/api/v1/admin/roles/{role_id}/permissions/{perm_id}")
        assert gr.status_code == 200, gr.text

        # Revoke permission
        rv = client.delete(f"/api/v1/admin/roles/{role_id}/permissions/{perm_id}")
        assert rv.status_code == 200, rv.text

        # Cleanup: delete role (non-system)
        dr = client.delete(f"/api/v1/admin/roles/{role_id}")
        assert dr.status_code == 200, dr.text

