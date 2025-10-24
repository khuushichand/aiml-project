import asyncio
import os
from typing import Tuple

import pytest
import asyncpg

from tldw_Server_API.app.core.AuthNZ.password_service import PasswordService

# Mirror the connection settings used by the AuthNZ fixtures without importing relatively
_TEST_DSN = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL") or ""
_TEST_DSN = _TEST_DSN.strip()

def _parse_pg_dsn(dsn: str):
    try:
        from urllib.parse import urlparse
        parsed = urlparse(dsn)
        if not parsed.scheme.startswith("postgres"):
            return None
        host = parsed.hostname or "localhost"
        port = int(parsed.port or 5432)
        user = parsed.username or "tldw_user"
        password = parsed.password or "TestPassword123!"
        return host, port, user, password
    except Exception:
        return None

_parsed = _parse_pg_dsn(_TEST_DSN) if _TEST_DSN else None
TEST_DB_HOST = (_parsed[0] if _parsed else os.getenv("TEST_DB_HOST", "localhost"))
TEST_DB_PORT = int(_parsed[1] if _parsed else int(os.getenv("TEST_DB_PORT", "5432")))
TEST_DB_USER = (_parsed[2] if _parsed else os.getenv("TEST_DB_USER", "tldw_user"))
TEST_DB_PASSWORD = (_parsed[3] if _parsed else os.getenv("TEST_DB_PASSWORD", "TestPassword123!"))

pytestmark = pytest.mark.integration


async def _ensure_admin(db_name: str) -> Tuple[str, str]:
    """Insert an admin user directly into the per-test Postgres DB and return (username, password)."""
    username = "admin"
    email = "admin@example.com"
    password = "Admin@Pass#2024!"
    ps = PasswordService()
    pw_hash = ps.hash_password(password)

    conn = await asyncpg.connect(
        host=TEST_DB_HOST,
        port=TEST_DB_PORT,
        user=TEST_DB_USER,
        password=TEST_DB_PASSWORD,
        database=db_name,
    )
    try:
        import uuid as _uuid
        admin_uuid = str(_uuid.uuid4())
        await conn.execute(
            """
            INSERT INTO users (uuid, username, email, password_hash, role, is_active, is_verified, storage_quota_mb, storage_used_mb)
            VALUES ($1, $2, $3, $4, 'admin', TRUE, TRUE, 10240, 0.0)
            ON CONFLICT (username) DO UPDATE SET role='admin'
            """,
            admin_uuid,
            username,
            email,
            pw_hash,
        )
    finally:
        await conn.close()

    return username, password


def _admin_headers(client, db_name: str):
    """Login as admin and return Authorization headers."""
    username, password = asyncio.run(_ensure_admin(db_name))
    lr = client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": password},
    )
    assert lr.status_code == 200, lr.text
    token = lr.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_list_roles_contains_seeded_roles(isolated_test_environment):
    client, db_name = isolated_test_environment
    headers = _admin_headers(client, db_name)

    r = client.get("/api/v1/admin/roles", headers=headers)
    assert r.status_code == 200, r.text
    roles = r.json()
    names = {role["name"] for role in roles}
    # Seeded roles should at least include admin and user (moderator/viewer may vary by migration)
    assert {"admin", "user"}.issubset(names)


def test_create_permission_and_assign_to_role(isolated_test_environment):
    client, db_name = isolated_test_environment
    headers = _admin_headers(client, db_name)

    # Create a new permission
    perm_code = "qa.run_checks"
    pr = client.post(
        "/api/v1/admin/permissions", headers=headers, json={"name": perm_code, "category": "qa"}
    )
    assert pr.status_code == 200, pr.text
    perm = pr.json()
    perm_id = perm["id"]

    # Create a role
    rr = client.post(
        "/api/v1/admin/roles", headers=headers, json={"name": "qa", "description": "QA role"}
    )
    assert rr.status_code == 200, rr.text
    role = rr.json()
    role_id = role["id"]

    # Grant permission to role
    gr = client.post(f"/api/v1/admin/roles/{role_id}/permissions/{perm_id}", headers=headers)
    assert gr.status_code == 200, gr.text

    # Revoke permission
    rv = client.delete(f"/api/v1/admin/roles/{role_id}/permissions/{perm_id}", headers=headers)
    assert rv.status_code == 200, rv.text

    # Cleanup: delete role (non-system)
    dr = client.delete(f"/api/v1/admin/roles/{role_id}", headers=headers)
    assert dr.status_code == 200, dr.text
