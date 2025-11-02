import os
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.mark.real_audit
@pytest.mark.integration
@pytest.mark.asyncio
async def test_org_membership_audit_events_postgres(tmp_path, real_audit_service, test_db_pool):
    # Use Postgres pool from fixture
    pool = test_db_pool

    # Disable CSRF for the TestClient
    from tldw_Server_API.app.core.config import settings as app_settings
    app_settings['CSRF_ENABLED'] = False

    # Ensure organizations table exists (idempotent)
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

    # Insert admin (role=admin, verified) and target user
    import uuid
    await pool.execute(
        "INSERT INTO users (uuid, username, email, password_hash, role, is_active, is_verified) VALUES ($1, $2, $3, $4, 'admin', TRUE, TRUE)",
        str(uuid.uuid4()), "pgadmin_org_audit", "pgadmin_org_audit@example.com", "x",
    )
    admin_id = await pool.fetchval("SELECT id FROM users WHERE username = $1", "pgadmin_org_audit")
    await pool.execute(
        "INSERT INTO users (uuid, username, email, password_hash, is_active, is_verified) VALUES ($1, $2, $3, $4, TRUE, TRUE)",
        str(uuid.uuid4()), "pgvictim_org", "pgvictim_org@example.com", "x",
    )
    target_id = await pool.fetchval("SELECT id FROM users WHERE username = $1", "pgvictim_org")

    # Create an API key for the admin user
    from tldw_Server_API.app.core.AuthNZ.api_key_manager import APIKeyManager
    mgr = APIKeyManager(pool)
    await mgr.initialize()
    key_info = await mgr.create_api_key(user_id=admin_id, name="admin-audit-key-org", scope="admin")
    admin_api_key = key_info['key']

    # Use TestClient and call admin org membership endpoints with X-API-KEY
    from tldw_Server_API.app.main import app
    headers = {"X-API-KEY": admin_api_key}

    with TestClient(app) as client:
        # Create org
        r = client.post("/api/v1/admin/orgs", json={"name": "Audit Org PG Org"}, headers=headers)
        assert r.status_code == 200, r.text
        org = r.json()

        # Add org member (org_member.add)
        r = client.post(
            f"/api/v1/admin/orgs/{org['id']}/members",
            json={"user_id": int(target_id), "role": "member"},
            headers=headers,
        )
        assert r.status_code == 200, r.text

        # Update org member role (org_member.update)
        r = client.patch(
            f"/api/v1/admin/orgs/{org['id']}/members/{int(target_id)}",
            json={"role": "admin"},
            headers=headers,
        )
        assert r.status_code == 200, r.text

        # Remove org member (org_member.remove)
        r = client.delete(
            f"/api/v1/admin/orgs/{org['id']}/members/{int(target_id)}",
            headers=headers,
        )
        assert r.status_code == 200, r.text

    # Verify audit events for the acting user in their per-user audit DB
    from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
    audit_db = DatabasePaths.get_audit_db_path(int(admin_id))
    assert audit_db.exists(), f"Audit DB not found: {audit_db}"

    con = sqlite3.connect(str(audit_db))
    try:
        for action in ("org_member.add", "org_member.update", "org_member.remove"):
            cur = con.execute("SELECT COUNT(*) FROM audit_events WHERE action = ?", (action,))
            cnt = cur.fetchone()[0]
            assert cnt >= 1, f"Expected >=1 audit events for action {action}"
    finally:
        con.close()
