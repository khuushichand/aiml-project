import asyncio
import os
from typing import Tuple

import pytest
import asyncpg

from tldw_Server_API.app.core.AuthNZ.password_service import PasswordService
from tldw_Server_API.tests.helpers.pg_env import get_pg_env

# Mirror the connection settings used by the AuthNZ fixtures without importing relatively
_pg = get_pg_env()
TEST_DB_HOST = _pg.host
TEST_DB_PORT = int(_pg.port)
TEST_DB_USER = _pg.user
TEST_DB_PASSWORD = _pg.password

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
        # Upsert user row with role hint; RBAC checks use user_roles, so also ensure mapping exists.
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
        # Ensure admin role mapping in user_roles for RBAC checks
        user_row = await conn.fetchrow("SELECT id FROM users WHERE username=$1", username)
        role_row = await conn.fetchrow("SELECT id FROM roles WHERE name='admin'")
        if user_row and role_row:
            await conn.execute(
                """
                INSERT INTO user_roles (user_id, role_id)
                VALUES ($1, $2)
                ON CONFLICT (user_id, role_id) DO NOTHING
                """,
                int(user_row["id"]),
                int(role_row["id"]),
            )
    finally:
        await conn.close()

    return username, password


def _admin_headers(client, db_name: str):
    """Login as admin and return Authorization headers.

    Safe to call from both sync and async pytest contexts. When an event loop
    is already running (pytest.mark.asyncio), run the async DB bootstrap in a
    dedicated thread to avoid nested-loop errors.
    """
    try:
        # If there is a running loop, execute the coroutine in a separate thread
        asyncio.get_running_loop()
        import threading

        result: dict = {}

        def _runner():

                     result["creds"] = asyncio.run(_ensure_admin(db_name))

        t = threading.Thread(target=_runner, daemon=True)
        t.start()
        t.join()
        username, password = result["creds"]
    except RuntimeError:
        # No loop running; safe to use asyncio.run directly
        username, password = asyncio.run(_ensure_admin(db_name))
    lr = client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": password},
    )
    assert lr.status_code == 200, lr.text
    token = lr.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _user_headers(client, suffix: str = ""):
    """Register/login a non-admin user and return Authorization headers."""
    username = f"user_{suffix or 'perm'}"
    email = f"{username}@example.com"
    password = "User@Pass#2024!"
    rr = client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    assert rr.status_code == 200, rr.text
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


def test_admin_roles_require_auth_and_admin(isolated_test_environment):


     client, db_name = isolated_test_environment
    anon = client.get("/api/v1/admin/roles")
    assert anon.status_code == 401

    user_headers = _user_headers(client, suffix="claims")
    as_user = client.get("/api/v1/admin/roles", headers=user_headers)
    assert as_user.status_code == 403

    admin_headers = _admin_headers(client, db_name)
    as_admin = client.get("/api/v1/admin/roles", headers=admin_headers)
    assert as_admin.status_code == 200, as_admin.text
    assert isinstance(as_admin.json(), list)
