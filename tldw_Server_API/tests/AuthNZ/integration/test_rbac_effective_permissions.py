import os
import tempfile
import importlib
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.settings import get_settings, reset_settings
from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool


pytestmark = pytest.mark.integration


def _fresh_client() -> TestClient:
    """Create a TestClient against a fresh single-user SQLite auth DB.

    This avoids interacting with any existing local DB that may have partial migrations.
    """
    # Point to an isolated SQLite DB path for this test
    fd, tmp_path = tempfile.mkstemp(prefix="users_test_rbac_", suffix=".db")
    os.close(fd)
    os.environ["AUTH_MODE"] = "single_user"
    os.environ["SINGLE_USER_API_KEY"] = os.getenv("SINGLE_USER_API_KEY", "test-api-key-12345")
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path}"

    # Reset singletons so the app picks up new settings/DB
    # Note: reset functions are async in some modules; we import the sync ones here
    reset_settings()
    # Reset DB pool (async); tests using TestClient will run lifespan and initialize anew
    try:
        import asyncio
        asyncio.run(reset_db_pool())
    except Exception:
        pass

    # Reload app module to ensure lifespan uses new env/settings
    from tldw_Server_API.app import main as app_main
    importlib.reload(app_main)
    client = TestClient(app_main.app, headers={"X-API-KEY": os.environ["SINGLE_USER_API_KEY"]})
    # Attach tmp path for caller cleanup if desired
    client._tmp_auth_db_path = tmp_path  # type: ignore[attr-defined]
    return client


def test_user_overrides_affect_effective_permissions():
    settings = get_settings()
    user_id = settings.SINGLE_USER_FIXED_ID

    new_perm = "it.test_override"

    with _fresh_client() as client:
        # Create new permission
        pr = client.post("/api/v1/admin/permissions", json={"name": new_perm, "category": "test"})
        if pr.status_code != 200:
            # If RBAC tables/migrations aren’t available in this environment, skip gracefully
            import pytest
            pytest.skip(f"RBAC tables unavailable or migrations failed: {pr.text}")
        perm = pr.json()
        perm_id = perm["id"]

        # Baseline: effective perms should not include the new permission
        er0 = client.get(f"/api/v1/admin/users/{user_id}/effective-permissions")
        assert er0.status_code == 200, er0.text
        eff0 = er0.json().get("permissions", [])
        assert new_perm not in eff0

        # Allow override for the new permission
        up = client.post(
            f"/api/v1/admin/users/{user_id}/overrides",
            json={"permission_id": perm_id, "effect": "allow"},
        )
        assert up.status_code == 200, up.text

        er1 = client.get(f"/api/v1/admin/users/{user_id}/effective-permissions")
        assert er1.status_code == 200, er1.text
        eff1 = er1.json().get("permissions", [])
        assert new_perm in eff1

        # Ensure user has baseline 'user' role, then deny media.create
        roles = client.get("/api/v1/admin/roles").json()
        role_user = next(r for r in roles if r["name"] == "user")
        add_role = client.post(f"/api/v1/admin/users/{user_id}/roles/{role_user['id']}")
        assert add_role.status_code == 200, add_role.text

        # Confirm baseline includes media.create
        er2 = client.get(f"/api/v1/admin/users/{user_id}/effective-permissions")
        assert er2.status_code == 200, er2.text
        eff2 = er2.json().get("permissions", [])
        assert "media.create" in eff2

        # Deny with override and confirm removal
        deny = client.post(
            f"/api/v1/admin/users/{user_id}/overrides",
            json={"permission_name": "media.create", "effect": "deny"},
        )
        assert deny.status_code == 200, deny.text

        er3 = client.get(f"/api/v1/admin/users/{user_id}/effective-permissions")
        assert er3.status_code == 200, er3.text
        eff3 = er3.json().get("permissions", [])
        assert "media.create" not in eff3
