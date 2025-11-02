"""
test_multi_user_onboarding.py
Description: Validate multi-user onboarding flow and role-restricted access.

Flow (multi_user mode only):
 - Register a user
 - Login and call a user-level endpoint
 - Verify admin endpoint is forbidden (403) for non-admin
 - Optionally, if ADMIN_TOKEN provided, verify admin access works
"""

import os
import pytest
import httpx

from .fixtures import api_client, test_user_credentials


@pytest.mark.multi_user
def test_multi_user_register_login_and_admin_access(api_client, test_user_credentials):
    # Determine auth mode via health or environment
    info = api_client.health_check()
    mode_env = os.getenv("AUTH_MODE", "").lower()
    if (info.get("auth_mode") or mode_env) not in {"multi_user", "multi-user", "multiuser"}:
        pytest.skip("Not in multi_user mode")

    # 1) Register
    try:
        reg = api_client.register(
            username=test_user_credentials["username"],
            email=test_user_credentials["email"],
            password=test_user_credentials["password"],
        )
        assert isinstance(reg, dict)
    except httpx.HTTPStatusError as e:
        # If registration disabled or user already exists, proceed to login
        if e.response.status_code not in (400, 409):
            raise

    # 2) Login
    login = api_client.login(
        username=test_user_credentials["username"],
        password=test_user_credentials["password"],
    )
    assert "access_token" in login or "token" in login

    # 3) Call a user-level endpoint (notes list)
    r = api_client.client.get("/api/v1/notes/?limit=1&offset=0")
    # Notes may require setup; accept 200 or 404
    assert r.status_code in (200, 404)

    # 4) Verify admin endpoint forbidden for non-admin
    admin = api_client.client.get("/api/v1/admin/users")
    assert admin.status_code == 403

    # 5) Optional: if ADMIN_TOKEN provided, verify admin access
    admin_token = os.getenv("E2E_ADMIN_BEARER")
    if admin_token:
        # Use admin bearer for Authorization
        headers = {"Authorization": f"Bearer {admin_token}"}
        r2 = api_client.client.get("/api/v1/admin/users", headers=headers)
        assert r2.status_code == 200
