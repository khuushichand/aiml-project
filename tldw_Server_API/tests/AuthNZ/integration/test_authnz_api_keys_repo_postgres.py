from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest

from tldw_Server_API.app.core.AuthNZ.repos.api_keys_repo import AuthnzApiKeysRepo
from tldw_Server_API.app.core.AuthNZ.api_key_manager import APIKeyManager, APIKeyStatus


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_authnz_api_keys_repo_rotation_and_revoke_postgres(test_db_pool):
    """AuthnzApiKeysRepo mark_rotated / revoke_api_key_for_user should work on Postgres."""
    pool = test_db_pool

    # Seed a user row for FK
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (
                uuid,
                username,
                email,
                password_hash,
                role,
                is_active,
                is_verified,
                storage_quota_mb,
                storage_used_mb,
                created_at
            )
            VALUES ($1, $2, $3, $4, $5, TRUE, TRUE, 5120, 0.0, $6)
            """,
            str(uuid.uuid4()),
            "pg_api_keys_repo_user",
            "pg_api_keys_repo_user@example.com",
            "x",
            "user",
            datetime.now(timezone.utc),
        )

    user_id = await pool.fetchval(
        "SELECT id FROM users WHERE username = $1",
        "pg_api_keys_repo_user",
    )
    assert user_id is not None
    user_id_int = int(user_id)

    mgr = APIKeyManager(pool)
    await mgr.initialize()

    first = await mgr.create_api_key(user_id=user_id_int, name="pg-first")
    second = await mgr.create_api_key(user_id=user_id_int, name="pg-second")
    first_id = int(first["id"])
    second_id = int(second["id"])

    repo = AuthnzApiKeysRepo(db_pool=pool)

    # mark_rotated: first -> second
    await repo.mark_rotated(
        old_key_id=first_id,
        new_key_id=second_id,
        rotated_status=APIKeyStatus.ROTATED.value,
        reason="PG rotation",
        revoked_at=datetime.now(timezone.utc),
    )

    row_first = await pool.fetchrow(
        "SELECT status, rotated_to, revoke_reason FROM api_keys WHERE id = $1",
        first_id,
    )
    row_second = await pool.fetchrow(
        "SELECT rotated_from FROM api_keys WHERE id = $1",
        second_id,
    )
    assert row_first is not None
    assert row_second is not None
    assert row_first["status"] == APIKeyStatus.ROTATED.value
    assert int(row_first["rotated_to"]) == second_id
    assert row_first["revoke_reason"] == "PG rotation"
    assert int(row_second["rotated_from"]) == first_id

    # revoke_api_key_for_user: revoke second key
    revoked = await repo.revoke_api_key_for_user(
        key_id=second_id,
        user_id=user_id_int,
        revoked_status=APIKeyStatus.REVOKED.value,
        active_status=APIKeyStatus.ACTIVE.value,
        reason="PG revoke",
        revoked_at=datetime.now(timezone.utc),
    )
    assert revoked is True

    row_second_after = await pool.fetchrow(
        """
        SELECT status, revoked_by, revoke_reason
        FROM api_keys
        WHERE id = $1
        """,
        second_id,
    )
    assert row_second_after is not None
    assert row_second_after["status"] == APIKeyStatus.REVOKED.value
    assert int(row_second_after["revoked_by"]) == user_id_int
    assert row_second_after["revoke_reason"] == "PG revoke"

