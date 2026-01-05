import asyncio
import os
import sqlite3
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


async def _await_audit_action(audit_db: Path, action: str, timeout_s: float = 5.0) -> int:
    deadline = time.monotonic() + timeout_s
    count = 0
    while time.monotonic() < deadline:
        with sqlite3.connect(str(audit_db)) as con:
            cur = con.execute("SELECT COUNT(*) FROM audit_events WHERE action = ?", (action,))
            count = cur.fetchone()[0]
        if count >= 1:
            break
        await asyncio.sleep(0.05)
    return count


def _flush_audit_events(client: TestClient, user_id: int) -> None:
    async def _flush(uid: int) -> None:
        from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import get_or_create_audit_service_for_user_id

        svc = await get_or_create_audit_service_for_user_id(uid)
        await svc.flush()

    if getattr(client, "portal", None) is not None:
        client.portal.call(_flush, int(user_id))


@pytest.mark.real_audit
@pytest.mark.integration
@pytest.mark.asyncio
async def test_org_membership_audit_events_postgres(tmp_path, real_audit_service, test_db_pool, monkeypatch):
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

    # Override AuthPrincipal to treat this user as admin for claim-first gates
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal
    from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal, AuthContext
    from starlette.requests import Request

    async def _principal_override(request: Request) -> AuthPrincipal:  # type: ignore[override]
        principal = AuthPrincipal(
            kind="user",
            user_id=admin_id,
            api_key_id=None,
            subject="pgadmin_org_audit",
            token_type="access",
            jti=None,
            roles=["admin"],
            permissions=["system.configure"],
            is_admin=True,
            org_ids=[],
            team_ids=[],
        )
        if request is not None:
            try:
                request.state.auth = AuthContext(
                    principal=principal,
                    ip=None,
                    user_agent=None,
                    request_id=None,
                )
                request.state.user_id = admin_id
            except Exception:
                # Best-effort; do not fail tests if state attachment fails
                pass
        return principal

    app.dependency_overrides[get_auth_principal] = _principal_override

    with TestClient(app) as client:
        # Create org
        r = client.post("/api/v1/admin/orgs", json={"name": "Audit Org PG Org"})
        assert r.status_code == 200, r.text
        org = r.json()

        # Add org member (org_member.add)
        r = client.post(
            f"/api/v1/admin/orgs/{org['id']}/members",
            json={"user_id": int(target_id), "role": "member"},
        )
        assert r.status_code == 200, r.text

        # Update org member role (org_member.update)
        r = client.patch(
            f"/api/v1/admin/orgs/{org['id']}/members/{int(target_id)}",
            json={"role": "admin"},
        )
        assert r.status_code == 200, r.text

        # Remove org member (org_member.remove)
        r = client.delete(
            f"/api/v1/admin/orgs/{org['id']}/members/{int(target_id)}",
        )
        assert r.status_code == 200, r.text

        _flush_audit_events(client, int(admin_id))

    app.dependency_overrides.pop(get_auth_principal, None)

    # Verify audit events for the acting user in their per-user audit DB
    from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import shutdown_all_audit_services
    await shutdown_all_audit_services()

    from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
    audit_db = DatabasePaths.get_audit_db_path(int(admin_id))
    assert audit_db.exists(), f"Audit DB not found: {audit_db}"

    for action in ("org_member.add", "org_member.update", "org_member.remove"):
        cnt = await _await_audit_action(audit_db, action)
        assert cnt >= 1, f"Expected >=1 audit events for action {action}"
