import pytest
import uuid

from tldw_Server_API.app.core.AuthNZ.api_key_manager import APIKeyManager
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool


@pytest.mark.asyncio
async def test_api_key_rotation_and_audit_sqlite():
    pool = await get_db_pool()

    # Ensure a user exists (minimal row)
    # Use a unique username/email per test run to avoid collisions with
    # prior executions against the shared sqlite users.db
    uname = f"akuser_{uuid.uuid4().hex[:8]}"
    email = f"{uname}@example.com"

    await pool.execute(
        """
        INSERT INTO users (username, email, password_hash, is_active)
        VALUES (?, ?, ?, 1)
        """,
        (uname, email, "x"),
    )
    user_row = await pool.fetchone("SELECT id FROM users WHERE username = ?", uname)
    user_id = user_row["id"] if isinstance(user_row, dict) else user_row[0]

    mgr = APIKeyManager()
    await mgr.initialize()

    # Create key
    created = await mgr.create_api_key(user_id=user_id, name="k1", description="d1", scope="read")
    key_id = created["id"]

    # Rotate key
    rotated = await mgr.rotate_api_key(key_id=key_id, user_id=user_id)
    assert rotated["id"] != key_id

    # Revoke new key
    ok = await mgr.revoke_api_key(rotated["id"], user_id=user_id, reason="cleanup")
    assert ok is True

    # Audit log should have entries
    rows = await pool.fetchall("SELECT COUNT(*) AS c FROM api_key_audit_log")
    count = rows[0]["c"] if isinstance(rows[0], dict) else rows[0][0]
    assert count >= 2
