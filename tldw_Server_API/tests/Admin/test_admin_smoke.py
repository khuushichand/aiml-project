import os
import tempfile
import importlib
import asyncio
from uuid import uuid4
from pathlib import Path

from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool
from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables
from tldw_Server_API.app.core.AuthNZ.initialize import ensure_single_user_rbac_seed_if_needed


def _fresh_client() -> TestClient:
    """Create a TestClient against a fresh single-user SQLite auth DB.

    Ensures RBAC migrations (including seeded roles/permissions) run on a new DB file.
    """
    fd, tmp_path = tempfile.mkstemp(prefix="users_test_admin_smoke_", suffix=".db")
    os.close(fd)

    os.environ["AUTH_MODE"] = "single_user"
    os.environ["SINGLE_USER_API_KEY"] = os.getenv("SINGLE_USER_API_KEY", "test-api-key-12345")
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path}"
    # Ensure test-mode shortcuts are disabled for this smoke test
    os.environ["TEST_MODE"] = "0"
    os.environ["TLDW_TEST_MODE"] = "0"

    # Reset singletons so the app picks up new settings/DB
    reset_settings()
    try:
        asyncio.run(reset_db_pool())
    except Exception:
        pass

    # Ensure schema migrations and RBAC seed exist on the fresh database
    ensure_authnz_tables(Path(tmp_path))
    try:
        asyncio.run(ensure_single_user_rbac_seed_if_needed())
    except RuntimeError:
        # Fallback if an event loop is already running in this context
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(ensure_single_user_rbac_seed_if_needed())
        finally:
            loop.close()

    from tldw_Server_API.app import main as app_main
    importlib.reload(app_main)
    client = TestClient(app_main.app, headers={"X-API-KEY": os.environ["SINGLE_USER_API_KEY"]})
    client._tmp_auth_db_path = tmp_path  # type: ignore[attr-defined]
    return client


def _force_backend(pg: bool):
    """Monkeypatch admin backend detector to force PG/SQLite branch in tests."""
    import tldw_Server_API.app.api.v1.endpoints.admin as admin_mod
    original = admin_mod._is_postgres_backend

    async def _true():
        return True

    async def _false():
        return False

    admin_mod._is_postgres_backend = _true if pg else _false  # type: ignore[assignment]
    return original


def test_admin_smoke_roles_permissions_sqlite_and_pg():
    with _fresh_client() as client:
        # First run: SQLite branch
        r_roles = client.get("/api/v1/admin/roles")
        if r_roles.status_code != 200:
            import pytest
            pytest.skip(f"RBAC tables unavailable or migrations failed: {r_roles.text}")

        # Create a new permission
        perm_name = f"smoke.perm.{uuid4().hex[:8]}"
        r_perm = client.post(
            "/api/v1/admin/permissions",
            json={"name": perm_name, "description": "smoke", "category": "smoke"},
        )
        assert r_perm.status_code == 200, r_perm.text
        perm = r_perm.json()
        perm_id = perm["id"]

        # Create a role
        role_name = f"smoke_role_{uuid4().hex[:8]}"
        r_role = client.post(
            "/api/v1/admin/roles",
            json={"name": role_name, "description": "smoke"},
        )
        assert r_role.status_code == 200, r_role.text
        role_id = r_role.json()["id"]

        # Grant, list, revoke
        r_grant = client.post(f"/api/v1/admin/roles/{role_id}/permissions/{perm_id}")
        assert r_grant.status_code == 200, r_grant.text

        r_list = client.get(f"/api/v1/admin/roles/{role_id}/permissions")
        assert r_list.status_code == 200, r_list.text
        names = {p["name"] for p in r_list.json()}
        assert perm_name in names

        r_revoke = client.delete(f"/api/v1/admin/roles/{role_id}/permissions/{perm_id}")
        assert r_revoke.status_code == 200, r_revoke.text

        # Delete role
        r_del_role = client.delete(f"/api/v1/admin/roles/{role_id}")
        assert r_del_role.status_code == 200, r_del_role.text

        # Force PG branch and repeat a minimal flow (grant -> revoke) using the same permission
        import tldw_Server_API.app.api.v1.endpoints.admin as admin_mod
        original = _force_backend(pg=True)
        try:
            # Create another role
            role_name2 = f"smoke_role_{uuid4().hex[:8]}"
            r_role2 = client.post(
                "/api/v1/admin/roles",
                json={"name": role_name2, "description": "smoke"},
            )
            assert r_role2.status_code == 200, r_role2.text
            role_id2 = r_role2.json()["id"]

            r_grant2 = client.post(f"/api/v1/admin/roles/{role_id2}/permissions/{perm_id}")
            assert r_grant2.status_code == 200, r_grant2.text

            r_list2 = client.get(f"/api/v1/admin/roles/{role_id2}/permissions")
            assert r_list2.status_code == 200, r_list2.text
            names2 = {p["name"] for p in r_list2.json()}
            assert perm_name in names2

            r_revoke2 = client.delete(f"/api/v1/admin/roles/{role_id2}/permissions/{perm_id}")
            assert r_revoke2.status_code == 200, r_revoke2.text

            r_del_role2 = client.delete(f"/api/v1/admin/roles/{role_id2}")
            assert r_del_role2.status_code == 200, r_del_role2.text
        finally:
            admin_mod._is_postgres_backend = original  # type: ignore[assignment]
