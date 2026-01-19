import json
import os
from uuid import uuid4

import pytest


def _require_ok(resp, label: str) -> None:
    if not resp.ok:
        raise AssertionError(f"{label} failed: status={resp.status} body={resp.text()}")


@pytest.mark.e2e
@pytest.mark.multi_user
def test_authnz_multi_user_permissions_audit_workflow(browser):
    base_url = os.environ.get("E2E_MULTI_USER_BASE_URL")
    if not base_url:
        pytest.skip("Set E2E_MULTI_USER_BASE_URL to run multi-user workflow.")

    admin_token = os.environ.get("E2E_ADMIN_BEARER")
    if not admin_token:
        pytest.skip("E2E_ADMIN_BEARER not set; skipping multi-user workflow.")

    context = browser.new_context(base_url=base_url)
    try:
        request = context.request
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        health = request.get("/api/v1/health")
        _require_ok(health, "health check")
        if health.json().get("auth_mode") != "multi_user":
            pytest.skip("Server is not in multi_user mode.")

        suffix = uuid4().hex[:8]
        role_resp = request.post(
            "/api/v1/admin/roles",
            headers=admin_headers,
            json={
                "name": f"e2e_role_{suffix}",
                "description": "E2E multi-user role",
            },
        )
        _require_ok(role_resp, "create role")
        role_id = role_resp.json()["id"]

        perms_resp = request.get(
            "/api/v1/admin/permissions",
            headers=admin_headers,
            params={"search": "system.logs"},
        )
        _require_ok(perms_resp, "list permissions")
        permissions = perms_resp.json()
        perm = next((p for p in permissions if p.get("name") == "system.logs"), None)
        if not perm:
            pytest.skip("system.logs permission not seeded; skipping workflow.")
        perm_id = perm["id"]

        user_name = f"e2e_user_{suffix}"
        user_email = f"{user_name}@example.com"
        user_password = os.getenv("E2E_TEST_PASSWORD", "Tlp9!ZxVq8@M")
        user_resp = request.post(
            "/api/v1/admin/users",
            headers=admin_headers,
            json={
                "username": user_name,
                "email": user_email,
                "password": user_password,
                "role": "user",
                "is_active": True,
                "is_verified": True,
            },
        )
        _require_ok(user_resp, "create user")
        user_id = user_resp.json()["id"]

        login_resp = request.post(
            "/api/v1/auth/login",
            data={"username": user_name, "password": user_password},
        )
        _require_ok(login_resp, "login user")
        user_token = login_resp.json()["access_token"]

        denied = request.get(
            "/api/v1/audit/export",
            headers={"Authorization": f"Bearer {user_token}"},
            params={"format": "json", "max_rows": "1"},
        )
        assert denied.status in {401, 403}

        grant_resp = request.post(
            f"/api/v1/admin/roles/{role_id}/permissions/{perm_id}",
            headers=admin_headers,
        )
        _require_ok(grant_resp, "grant role permission")

        assign_resp = request.post(
            f"/api/v1/admin/users/{user_id}/roles/{role_id}",
            headers=admin_headers,
        )
        _require_ok(assign_resp, "assign role to user")

        effective_resp = request.get(
            f"/api/v1/admin/users/{user_id}/effective-permissions",
            headers=admin_headers,
        )
        _require_ok(effective_resp, "get effective permissions")
        effective = effective_resp.json().get("permissions", [])
        assert "system.logs" in effective

        relogin_resp = request.post(
            "/api/v1/auth/login",
            data={"username": user_name, "password": user_password},
        )
        _require_ok(relogin_resp, "re-login user")
        user_token = relogin_resp.json()["access_token"]

        audit_resp = request.get(
            "/api/v1/audit/export",
            headers={"Authorization": f"Bearer {user_token}"},
            params={"format": "json", "max_rows": "1"},
        )
        _require_ok(audit_resp, "export audit events")
        try:
            audit_payload = audit_resp.json()
        except Exception:
            audit_payload = json.loads(audit_resp.text())
        assert isinstance(audit_payload, list)

        cleanup_user = request.delete(
            f"/api/v1/admin/users/{user_id}",
            headers=admin_headers,
        )
        _require_ok(cleanup_user, "delete user")

        cleanup_role = request.delete(
            f"/api/v1/admin/roles/{role_id}",
            headers=admin_headers,
        )
        _require_ok(cleanup_role, "delete role")
    finally:
        context.close()
