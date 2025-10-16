import os
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.mark.real_audit
@pytest.mark.asyncio
async def test_admin_org_membership_audit_events_sqlite(tmp_path, real_audit_service):
    # Configure single-user mode with API key and user DB base
    os.environ['AUTH_MODE'] = 'single_user'
    os.environ['SINGLE_USER_API_KEY'] = 'audit-key-123'
    # real_audit_service fixture sets USER_DB_BASE_DIR and resets settings

    # Point AuthNZ DB at tmp path
    db_path = tmp_path / 'users.db'
    os.environ['DATABASE_URL'] = f'sqlite:///{db_path}'

    # Reset singletons and init schema
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool, get_db_pool
    from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables
    reset_settings()
    await reset_db_pool()

    pool = await get_db_pool()
    ensure_authnz_tables(Path(pool.db_path))

    # Create admin user (id should be 1 by default) and a target user
    async with pool.transaction() as conn:
        await conn.execute(
            "INSERT INTO users (username, email, password_hash, is_active) VALUES (?, ?, ?, 1)",
            ("single_user", "single@example.com", "x"),
        )
        await conn.execute(
            "INSERT INTO users (username, email, password_hash, is_active) VALUES (?, ?, ?, 1)",
            ("victim", "victim@example.com", "x"),
        )
    admin_id = await pool.fetchval("SELECT id FROM users WHERE username = ?", "single_user")
    target_id = await pool.fetchval("SELECT id FROM users WHERE username = ?", "victim")

    # Prepare app
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.core.config import settings as app_settings
    app_settings['CSRF_ENABLED'] = False

    with TestClient(app) as client:
        # Create org
        r = client.post("/api/v1/admin/orgs", json={"name": "Audit Org"}, headers={"X-API-KEY": os.environ['SINGLE_USER_API_KEY']})
        assert r.status_code == 200, r.text
        org = r.json()

        # Add member -> should log audit event for actor (single_user)
        r = client.post(
            f"/api/v1/admin/orgs/{org['id']}/members",
            json={"user_id": target_id, "role": "member"},
            headers={"X-API-KEY": os.environ['SINGLE_USER_API_KEY']}
        )
        assert r.status_code == 200, r.text

    # After client exits, app shutdown flushes audit events
    # Inspect user-specific audit DB
    from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
    audit_db = DatabasePaths.get_audit_db_path(int(admin_id))
    assert audit_db.exists(), f"Audit DB not found: {audit_db}"

    con = sqlite3.connect(str(audit_db))
    try:
        cur = con.execute("SELECT COUNT(*) FROM audit_events WHERE action = ?", ("org_member.add",))
        cnt = cur.fetchone()[0]
        assert cnt >= 1
    finally:
        con.close()
