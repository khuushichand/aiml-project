import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_endpoints_pg(setup_test_database):
    # App and overrides
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
    from tldw_Server_API.app.api.v1.API_Deps.auth_deps import require_admin
    from tldw_Server_API.app.core.AuthNZ.api_key_manager import APIKeyManager

    # Disable CSRF for test client
    from tldw_Server_API.app.core.config import settings as app_settings
    app_settings['CSRF_ENABLED'] = False

    # Ensure Postgres pool
    pool = await get_db_pool()

    # Ensure org/team/api_keys/usage tables exist
    await pool.execute(
        """
        CREATE TABLE IF NOT EXISTS organizations (
            id SERIAL PRIMARY KEY,
            uuid VARCHAR(64) UNIQUE,
            name VARCHAR(255) UNIQUE NOT NULL,
            slug VARCHAR(255) UNIQUE,
            owner_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            is_active BOOLEAN DEFAULT TRUE,
            metadata JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    await pool.execute(
        """
        CREATE TABLE IF NOT EXISTS teams (
            id SERIAL PRIMARY KEY,
            org_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            name VARCHAR(255) NOT NULL,
            slug VARCHAR(255),
            description TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            metadata JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (org_id, name)
        )
        """
    )
    await pool.execute(
        """
        CREATE TABLE IF NOT EXISTS team_members (
            team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role VARCHAR(32) DEFAULT 'member',
            status VARCHAR(32) DEFAULT 'active',
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (team_id, user_id)
        )
        """
    )
    await pool.execute(
        """
        CREATE TABLE IF NOT EXISTS llm_usage_log (
            id SERIAL PRIMARY KEY,
            ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            key_id INTEGER REFERENCES api_keys(id) ON DELETE SET NULL,
            endpoint TEXT,
            operation TEXT,
            provider TEXT,
            model TEXT,
            status INTEGER,
            latency_ms INTEGER,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            total_tokens INTEGER,
            prompt_cost_usd DOUBLE PRECISION,
            completion_cost_usd DOUBLE PRECISION,
            total_cost_usd DOUBLE PRECISION,
            currency TEXT DEFAULT 'USD',
            estimated BOOLEAN DEFAULT FALSE,
            request_id TEXT
        )
        """
    )

    # Ensure api_keys and virtual columns via manager
    mgr = APIKeyManager(pool)
    await mgr.initialize()

    # Insert admin user
    import uuid as _uuid
    await pool.execute(
        "INSERT INTO users (uuid, username, email, password_hash, is_active) VALUES ($1, $2, $3, $4, TRUE)",
        str(_uuid.uuid4()), "pgadmin", "pgadmin@example.com", "x",
    )
    user_id = await pool.fetchval("SELECT id FROM users WHERE username = $1", "pgadmin")

    # Override admin requirement
    async def _pass_admin():
        return {"id": user_id, "role": "admin", "username": "pgadmin"}
    app.dependency_overrides[require_admin] = _pass_admin

    with TestClient(app) as client:
        # Create org
        r = client.post("/api/v1/admin/orgs", json={"name": "Omega Org"})
        assert r.status_code == 200, r.text
        org = r.json()
        assert org['id'] > 0

        # Create team
        r = client.post(f"/api/v1/admin/orgs/{org['id']}/teams", json={"name": "Ops"})
        assert r.status_code == 200
        team = r.json()
        assert team['name'] == 'Ops'

        # Create virtual key
        r = client.post(
            f"/api/v1/admin/users/{user_id}/virtual-keys",
            json={
                "name": "pg-vk",
                "allowed_endpoints": ["chat.completions"],
                "budget_day_tokens": 300
            }
        )
        assert r.status_code == 200, r.text
        vk = r.json()
        assert 'key' in vk and vk['id'] > 0

        # List virtual keys
        r = client.get(f"/api/v1/admin/users/{user_id}/virtual-keys")
        assert r.status_code == 200
        arr = r.json()
        assert any(k['id'] == vk['id'] for k in arr)

    app.dependency_overrides.pop(require_admin, None)

