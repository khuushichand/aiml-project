import os
import tempfile
import importlib

from fastapi.testclient import TestClient

from pathlib import Path
from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool


def _fresh_client() -> TestClient:
    """Create a TestClient against a fresh single-user SQLite auth DB."""
    fd, tmp_path = tempfile.mkstemp(prefix="users_test_role_effective_", suffix=".db")
    os.close(fd)

    os.environ["AUTH_MODE"] = "single_user"
    os.environ["SINGLE_USER_API_KEY"] = os.getenv("SINGLE_USER_API_KEY", "test-api-key-12345")
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path}"

    reset_settings()
    try:
        import asyncio
        asyncio.run(reset_db_pool())
    except Exception:
        pass

    # Ensure SQLite AuthNZ schema exists (migrations) for the fresh DB
    try:
        from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables
        ensure_authnz_tables(Path(tmp_path))
    except Exception:
        pass

    from tldw_Server_API.app import main as app_main
    importlib.reload(app_main)
    client = TestClient(app_main.app, headers={"X-API-KEY": os.environ["SINGLE_USER_API_KEY"]})
    # Fallback: ensure RBAC seed for single-user SQLite if not already present
    try:
        from tldw_Server_API.app.core.AuthNZ.initialize import ensure_single_user_rbac_seed_if_needed
        import asyncio
        asyncio.run(ensure_single_user_rbac_seed_if_needed())
    except Exception:
        pass
    client._tmp_auth_db_path = tmp_path  # type: ignore[attr-defined]
    return client


def test_role_effective_permissions_sqlite():
    with _fresh_client() as client:
        # Locate the 'user' role
        r_roles = client.get("/api/v1/admin/roles")
        if r_roles.status_code != 200:
            import pytest
            pytest.skip(f"RBAC not available: {r_roles.text}")
        roles = r_roles.json()
        role_user = next((r for r in roles if r.get("name") == "user"), None)
        assert role_user is not None

        # Initial effective view
        r_eff = client.get(f"/api/v1/admin/roles/{role_user['id']}/permissions/effective")
        assert r_eff.status_code == 200, r_eff.text
        eff = r_eff.json()
        assert eff["role_id"] == role_user["id"]
        assert eff["role_name"] == role_user["name"]
        # Baseline seeded
        for expected in {"media.create", "media.read", "media.update", "media.transcribe", "users.read"}:
            assert expected in eff["permissions"], f"missing baseline {expected}"
        # No tool permissions by default
        assert isinstance(eff["tool_permissions"], list)

        # Grant a tool permission and verify
        r_grant = client.post(
            f"/api/v1/admin/roles/{role_user['id']}/permissions/tools",
            json={"tool_name": "example_tool"},
        )
        assert r_grant.status_code == 200, r_grant.text

        r_eff2 = client.get(f"/api/v1/admin/roles/{role_user['id']}/permissions/effective")
        assert r_eff2.status_code == 200
        eff2 = r_eff2.json()
        assert "tools.execute:example_tool" in eff2["tool_permissions"]
        # all_permissions should contain both categories
        union_set = set(eff2["permissions"]) | set(eff2["tool_permissions"])
        assert set(eff2["all_permissions"]) == union_set
