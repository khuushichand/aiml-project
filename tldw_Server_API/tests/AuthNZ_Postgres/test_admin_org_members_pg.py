import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_org_members_endpoints_postgres(test_db_pool):
    # App and overrides
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.api.v1.API_Deps.auth_deps import require_admin

    # Disable CSRF for test client
    from tldw_Server_API.app.core.config import settings as app_settings
    app_settings['CSRF_ENABLED'] = False

    pool = test_db_pool

    # Ensure org tables exist
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
    await pool.execute("CREATE INDEX IF NOT EXISTS idx_orgs_owner ON organizations(owner_user_id)")
    await pool.execute(
        """
        CREATE TABLE IF NOT EXISTS org_members (
            org_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role VARCHAR(32) DEFAULT 'member',
            status VARCHAR(32) DEFAULT 'active',
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (org_id, user_id)
        )
        """
    )
    await pool.execute("CREATE INDEX IF NOT EXISTS idx_org_members_user ON org_members(user_id)")
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

    # Insert admin and standard user
    import uuid
    await pool.execute(
        "INSERT INTO users (uuid, username, email, password_hash, is_active) VALUES ($1, $2, $3, $4, TRUE)",
        str(uuid.uuid4()), "pgadmin2", "pgadmin2@example.com", "x",
    )
    admin_id = await pool.fetchval("SELECT id FROM users WHERE username = $1", "pgadmin2")
    await pool.execute(
        "INSERT INTO users (uuid, username, email, password_hash, is_active) VALUES ($1, $2, $3, $4, TRUE)",
        str(uuid.uuid4()), "pgbob", "pgbob@example.com", "x",
    )
    bob_id = await pool.fetchval("SELECT id FROM users WHERE username = $1", "pgbob")
    await pool.execute(
        "INSERT INTO users (uuid, username, email, password_hash, is_active) VALUES ($1, $2, $3, $4, TRUE)",
        str(uuid.uuid4()), "pgcharlie", "pgcharlie@example.com", "x",
    )
    charlie_id = await pool.fetchval("SELECT id FROM users WHERE username = $1", "pgcharlie")

    # Override admin requirement
    async def _pass_admin():
        return {"id": admin_id, "role": "admin", "username": "pgadmin2"}
    app.dependency_overrides[require_admin] = _pass_admin

    with TestClient(app) as client:
        # Create org
        r = client.post("/api/v1/admin/orgs", json={"name": "Sigma Org"})
        assert r.status_code == 200, r.text
        org = r.json()

        # Add member (idempotent)
        r = client.post(f"/api/v1/admin/orgs/{org['id']}/members", json={"user_id": bob_id, "role": "member"})
        assert r.status_code == 200, r.text
        r2 = client.post(f"/api/v1/admin/orgs/{org['id']}/members", json={"user_id": bob_id, "role": "member"})
        assert r2.status_code == 200

        team_id = await pool.fetchval(
            "SELECT id FROM teams WHERE org_id = $1 AND name = $2",
            org['id'],
            "Default-Base",
        )
        assert team_id is not None
        member_count = await pool.fetchval(
            "SELECT COUNT(*) FROM team_members WHERE team_id = $1 AND user_id = $2",
            team_id,
            bob_id,
        )
        assert member_count == 1

        # User-centric listing
        r = client.get(f"/api/v1/admin/users/{bob_id}/org-memberships")
        assert r.status_code == 200
        assert any(m['org_id'] == org['id'] for m in r.json())

        # List members (filters)
        r = client.get(f"/api/v1/admin/orgs/{org['id']}/members", params={"role": "member"})
        assert r.status_code == 200
        assert any(m['user_id'] == bob_id for m in r.json())

        # Patch role
        r = client.patch(f"/api/v1/admin/orgs/{org['id']}/members/{bob_id}", json={"role": "admin"})
        assert r.status_code == 200
        assert r.json()['role'] == 'admin'

        # Filter by new role
        r = client.get(f"/api/v1/admin/orgs/{org['id']}/members", params={"role": "admin"})
        assert r.status_code == 200
        assert any(m['user_id'] == bob_id for m in r.json())

        # Remove member
        r = client.delete(f"/api/v1/admin/orgs/{org['id']}/members/{bob_id}")
        assert r.status_code == 200
        assert "Org member removed" in r.text
        # Removing again yields friendly message
        r = client.delete(f"/api/v1/admin/orgs/{org['id']}/members/{bob_id}")
        assert r.status_code == 200
        assert "No membership found" in r.text

        r = client.post(
            f"/api/v1/admin/orgs/{org['id']}/members",
            json={"user_id": charlie_id, "role": "owner"},
        )
        assert r.status_code == 200, r.text

        r = client.patch(
            f"/api/v1/admin/orgs/{org['id']}/members/{charlie_id}",
            json={"role": "admin"},
        )
        assert r.status_code == 400
        assert "retain at least one owner" in r.text.lower()

        r = client.delete(f"/api/v1/admin/orgs/{org['id']}/members/{charlie_id}")
        assert r.status_code == 400
        assert "retain at least one owner" in r.text.lower()

        remaining = await pool.fetchval(
            "SELECT COUNT(*) FROM team_members WHERE team_id = $1 AND user_id = $2",
            team_id,
            bob_id,
        )
        assert remaining == 0

    app.dependency_overrides.pop(require_admin, None)
