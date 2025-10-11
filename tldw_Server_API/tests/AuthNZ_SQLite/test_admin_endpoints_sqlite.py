import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.mark.asyncio
async def test_admin_endpoints_basic_sqlite(tmp_path):
    # Configure SQLite
    os.environ['AUTH_MODE'] = 'single_user'
    db_path = tmp_path / 'users.db'
    os.environ['DATABASE_URL'] = f'sqlite:///{db_path}'

    # Reset singletons
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool, get_db_pool
    from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables
    reset_settings()
    await reset_db_pool()

    # Disable CSRF for test client
    from tldw_Server_API.app.core.config import settings as app_settings
    app_settings['CSRF_ENABLED'] = False

    pool = await get_db_pool()
    ensure_authnz_tables(Path(pool.db_path))

    # Create a user to satisfy FK and for membership
    async with pool.transaction() as conn:
        await conn.execute(
            "INSERT INTO users (username, email, password_hash, is_active) VALUES (?, ?, ?, 1)",
            ("adminuser", "admin@example.com", "x"),
        )
    user_id = await pool.fetchval("SELECT id FROM users WHERE username = ?", "adminuser")

    # Create TestClient and override admin dependency to bypass auth
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.api.v1.API_Deps.auth_deps import require_admin

    async def _pass_admin():
        return {"id": user_id, "role": "admin", "username": "adminuser"}

    app.dependency_overrides[require_admin] = _pass_admin

    with TestClient(app) as client:
        # Create org
        r = client.post("/api/v1/admin/orgs", json={"name": "Zeta Org"})
        assert r.status_code == 200, r.text
        org = r.json()
        assert org['id'] > 0 and org['name'] == 'Zeta Org'

        # List orgs
        r = client.get("/api/v1/admin/orgs")
        assert r.status_code == 200
        assert any(o['name'] == 'Zeta Org' for o in r.json())

        # Create a team
        r = client.post(f"/api/v1/admin/orgs/{org['id']}/teams", json={"name": "Infra"})
        assert r.status_code == 200
        team = r.json()
        assert team['name'] == 'Infra'

        # Create a virtual key for admin user with small budget
        r = client.post(
            f"/api/v1/admin/users/{user_id}/virtual-keys",
            json={
                "name": "vk-admin",
                "allowed_endpoints": ["chat.completions"],
                "budget_day_tokens": 500
            }
        )
        assert r.status_code == 200
        vk = r.json()
        assert 'key' in vk and vk['id'] > 0

        # List virtual keys for user
        r = client.get(f"/api/v1/admin/users/{user_id}/virtual-keys")
        assert r.status_code == 200
        arr = r.json()
        assert any(k['id'] == vk['id'] for k in arr)

    # Cleanup overrides
    app.dependency_overrides.pop(require_admin, None)
