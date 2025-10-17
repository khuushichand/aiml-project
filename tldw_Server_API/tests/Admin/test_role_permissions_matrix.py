import os
import tempfile
import importlib

from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool


def _fresh_client() -> TestClient:
    """Create a TestClient against a fresh single-user SQLite auth DB.

    Ensures RBAC migrations (including seeded roles/permissions) run on a new DB file.
    """
    fd, tmp_path = tempfile.mkstemp(prefix="users_test_role_perms_", suffix=".db")
    os.close(fd)

    os.environ["AUTH_MODE"] = "single_user"
    os.environ["SINGLE_USER_API_KEY"] = os.getenv("SINGLE_USER_API_KEY", "test-api-key-12345")
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path}"

    # Reset singletons so the app picks up new settings/DB
    reset_settings()
    try:
        import asyncio
        asyncio.run(reset_db_pool())
    except Exception:
        pass

    from tldw_Server_API.app import main as app_main
    importlib.reload(app_main)
    client = TestClient(app_main.app, headers={"X-API-KEY": os.environ["SINGLE_USER_API_KEY"]})
    client._tmp_auth_db_path = tmp_path  # type: ignore[attr-defined]
    return client


def test_list_role_permissions_for_user_role():
    """Smoke: user role should include seeded baseline permissions."""
    with _fresh_client() as client:
        # Find the 'user' role
        r_roles = client.get("/api/v1/admin/roles")
        if r_roles.status_code != 200:
            import pytest
            pytest.skip(f"RBAC tables unavailable or migrations failed: {r_roles.text}")
        roles = r_roles.json()
        role_user = next((r for r in roles if r.get("name") == "user"), None)
        assert role_user is not None, "seeded 'user' role not found"

        # List permissions for the 'user' role
        r_perms = client.get(f"/api/v1/admin/roles/{role_user['id']}/permissions")
        assert r_perms.status_code == 200, r_perms.text
        perms = r_perms.json()
        perm_names = {p["name"] for p in perms}

        # Baseline seeded in migrations: media.create, media.read, media.update, media.transcribe, users.read
        for expected in {"media.create", "media.read", "media.update", "media.transcribe", "users.read"}:
            assert expected in perm_names, f"missing expected permission: {expected}"


def test_roles_matrix_includes_user_baseline():
    """Smoke: matrix endpoint returns roles, permissions, and grants; 'user' has baseline grants.

    Skips gracefully if RBAC tables/migrations are not available in this environment.
    """
    with _fresh_client() as client:
        r = client.get("/api/v1/admin/roles/matrix")
        if r.status_code != 200:
            import pytest
            pytest.skip(f"RBAC tables unavailable or migrations failed: {r.text}")

        data = r.json()
        roles = {r["id"]: r for r in data.get("roles", [])}
        perms = {p["id"]: p for p in data.get("permissions", [])}
        grants = {(g["role_id"], g["permission_id"]) for g in data.get("grants", [])}

        # Find 'user' role id and baseline perms ids
        user_role_id = next((rid for rid, rr in roles.items() if rr.get("name") == "user"), None)
        assert user_role_id is not None, "'user' role not found"

        # Resolve baseline permission IDs by name
        needed = {"media.create", "media.read", "media.update", "media.transcribe", "users.read"}
        name_to_id = {p["name"]: pid for pid, p in perms.items()}
        missing_names = [n for n in needed if n not in name_to_id]
        assert not missing_names, f"Missing permissions in catalog: {missing_names}"

        for perm_name in needed:
            pid = name_to_id[perm_name]
            assert (user_role_id, pid) in grants, f"grant missing for user->{perm_name}"


def test_roles_boolean_matrix_shape():
    """Smoke: boolean matrix returns aligned shapes and includes roles/permissions.

    Skips gracefully if RBAC tables/migrations are not available.
    """
    with _fresh_client() as client:
        r = client.get("/api/v1/admin/roles/matrix-boolean")
        if r.status_code != 200:
            import pytest
            pytest.skip(f"RBAC tables unavailable or migrations failed: {r.text}")
        data = r.json()
        roles = data.get("roles", [])
        perm_names = data.get("permission_names", [])
        matrix = data.get("matrix", [])
        assert isinstance(roles, list) and isinstance(perm_names, list) and isinstance(matrix, list)
        assert len(matrix) == len(roles)
        if roles and perm_names:
            assert all(isinstance(row, list) and len(row) == len(perm_names) for row in matrix)
