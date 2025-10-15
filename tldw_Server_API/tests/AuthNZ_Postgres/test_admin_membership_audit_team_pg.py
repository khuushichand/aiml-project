import os
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.mark.real_audit
@pytest.mark.integration
@pytest.mark.asyncio
async def test_team_membership_audit_events_postgres(tmp_path, real_audit_service, test_db_pool):
    # Use Postgres pool from fixture
    pool = test_db_pool

    # Disable CSRF for the TestClient
    from tldw_Server_API.app.core.config import settings as app_settings
    app_settings['CSRF_ENABLED'] = False

    # Ensure org/team/member tables exist (idempotent)
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

    # Insert admin (role=admin) and target user
    import uuid
    await pool.execute(
        "INSERT INTO users (uuid, username, email, password_hash, role, is_active, is_verified) VALUES ($1, $2, $3, $4, 'admin', TRUE, TRUE)",
        str(uuid.uuid4()), "pgadmin_audit", "pgadmin_audit@example.com", "x",
    )
    admin_id = await pool.fetchval("SELECT id FROM users WHERE username = $1", "pgadmin_audit")
    await pool.execute(
        "INSERT INTO users (uuid, username, email, password_hash, is_active) VALUES ($1, $2, $3, $4, TRUE)",
        str(uuid.uuid4()), "pgvictim", "pgvictim@example.com", "x",
    )
    target_id = await pool.fetchval("SELECT id FROM users WHERE username = $1", "pgvictim")

    # Create an API key for the admin user (so request.state.user_id is set)
    from tldw_Server_API.app.core.AuthNZ.api_key_manager import APIKeyManager
    mgr = APIKeyManager(pool)
    await mgr.initialize()
    key_info = await mgr.create_api_key(user_id=admin_id, name="admin-audit-key", scope="admin")
    admin_api_key = key_info['key']

    # Use TestClient and call admin endpoints with X-API-KEY
    from tldw_Server_API.app.main import app
    headers = {"X-API-KEY": admin_api_key}

    with TestClient(app) as client:
        # Create org
        r = client.post("/api/v1/admin/orgs", json={"name": "Audit Org PG"}, headers=headers)
        assert r.status_code == 200, r.text
        org = r.json()

        # Create team
        r = client.post(f"/api/v1/admin/orgs/{org['id']}/teams", json={"name": "QA-PG"}, headers=headers)
        assert r.status_code == 200, r.text
        team = r.json()

        # Add team member -> should log audit event for actor (admin)
        r = client.post(
            f"/api/v1/admin/teams/{team['id']}/members",
            json={"user_id": int(target_id), "role": "member"},
            headers=headers,
        )
        assert r.status_code == 200, r.text

    # After client exits, the app shuts down and flushes audit events
    from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
    audit_db = DatabasePaths.get_audit_db_path(int(admin_id))
    assert audit_db.exists(), f"Audit DB not found: {audit_db}"

    con = sqlite3.connect(str(audit_db))
    try:
        cur = con.execute("SELECT COUNT(*) FROM audit_events WHERE action = ?", ("team_member.add",))
        cnt = cur.fetchone()[0]
        assert cnt >= 1
    finally:
        con.close()
