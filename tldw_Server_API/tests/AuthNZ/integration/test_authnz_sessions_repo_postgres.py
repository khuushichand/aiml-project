from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

import pytest

from tldw_Server_API.app.core.AuthNZ.repos.sessions_repo import AuthnzSessionsRepo


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_authnz_sessions_repo_validation_and_refresh_postgres(test_db_pool):
    """AuthnzSessionsRepo validation/refresh helpers should work on Postgres."""
    pool = test_db_pool

    # Seed a user row for FK
    created_at = datetime.utcnow().replace(microsecond=0)
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
            "pg_sessions_user",
            "pg_sessions_user@example.com",
            "x",
            "user",
            created_at,
        )

    user_id = await pool.fetchval(
        "SELECT id FROM users WHERE username = $1",
        "pg_sessions_user",
    )
    assert user_id is not None

    repo = AuthnzSessionsRepo(pool)

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=1)
    refresh_expires = now + timedelta(days=7)

    # Create a session record with known hashes
    session_id = await repo.create_session_record(
        user_id=int(user_id),
        token_hash="hash-access",
        refresh_token_hash="hash-refresh",
        encrypted_token="enc-access",
        encrypted_refresh="enc-refresh",
        expires_at=expires_at,
        refresh_expires_at=refresh_expires,
        ip_address="127.0.0.1",
        user_agent="pytest-pg",
        device_id="pg-device-1",
        access_jti="access-jti",
        refresh_jti="refresh-jti",
    )
    assert session_id > 0

    # Validation helpers: by id and by token hash
    by_id = await repo.fetch_session_for_validation_by_id(session_id)
    assert by_id is not None
    assert by_id["id"] == session_id
    assert by_id["user_id"] == int(user_id)
    assert bool(by_id["user_active"]) is True

    by_hash = await repo.fetch_session_for_validation_by_token_hash("hash-access")
    assert by_hash is not None
    assert by_hash["id"] == session_id

    missing = await repo.fetch_session_for_validation_by_id(session_id + 1)
    assert missing is None

    # Refresh helpers: find by refresh hash candidates and update tokens
    found = await repo.find_active_session_by_refresh_hash_candidates(
        ["does-not-exist", "hash-refresh"]
    )
    assert found is not None
    assert found["id"] == session_id
    assert found["user_id"] == int(user_id)

    new_expires = now + timedelta(hours=2)
    await repo.update_session_tokens_for_refresh(
        session_id=found["id"],
        new_access_hash="hash-access-new",
        access_jti="access-jti-new",
        expires_at=new_expires,
        encrypted_access_token="enc-access-new",
        refresh_hash_update="hash-refresh-new",
        refresh_jti="refresh-jti-new",
        refresh_expires_at=refresh_expires,
        encrypted_refresh_token="enc-refresh-new",
    )

    row = await pool.fetchrow(
        """
        SELECT token_hash,
               refresh_token_hash,
               access_jti,
               refresh_jti,
               encrypted_token,
               encrypted_refresh
        FROM sessions
        WHERE id = $1
        """,
        session_id,
    )
    assert row is not None
    assert row["token_hash"] == "hash-access-new"
    assert row["refresh_token_hash"] == "hash-refresh-new"
    assert row["access_jti"] == "access-jti-new"
    assert row["refresh_jti"] == "refresh-jti-new"
    assert row["encrypted_token"] == "enc-access-new"
    assert row["encrypted_refresh"] == "enc-refresh-new"


@pytest.mark.asyncio
async def test_authnz_sessions_repo_bulk_revocation_postgres(test_db_pool):
    """AuthnzSessionsRepo bulk revocation helpers should work on Postgres."""
    pool = test_db_pool

    # Seed a user row for FK
    created_at = datetime.utcnow().replace(microsecond=0)
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
            "pg_sessions_bulk_user",
            "pg_sessions_bulk_user@example.com",
            "x",
            "user",
            created_at,
        )

    user_id = await pool.fetchval(
        "SELECT id FROM users WHERE username = $1",
        "pg_sessions_bulk_user",
    )
    assert user_id is not None

    repo = AuthnzSessionsRepo(pool)

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=1)
    refresh_expires = now + timedelta(days=7)

    for idx in range(2):
        await repo.create_session_record(
            user_id=int(user_id),
            token_hash=f"hash-access-bulk-{idx}",
            refresh_token_hash=f"hash-refresh-bulk-{idx}",
            encrypted_token=f"enc-access-bulk-{idx}",
            encrypted_refresh=f"enc-refresh-bulk-{idx}",
            expires_at=expires_at,
            refresh_expires_at=refresh_expires,
            ip_address="127.0.0.1",
            user_agent=f"pytest-pg-bulk-{idx}",
            device_id=f"pg-device-bulk-{idx}",
            access_jti=f"access-jti-bulk-{idx}",
            refresh_jti=f"refresh-jti-bulk-{idx}",
        )

    sessions = await repo.fetch_session_token_metadata_for_user(int(user_id))
    assert len(sessions) >= 2

    affected = await repo.mark_sessions_revoked_for_user_with_audit(
        user_id=int(user_id),
        revoked_by=int(user_id),
        reason="bulk-logout",
    )
    assert affected >= 2

    rows = await pool.fetch(
        """
        SELECT is_active, is_revoked, revoked_by, revoke_reason
        FROM sessions
        WHERE user_id = $1
        """,
        int(user_id),
    )
    assert rows
    for row in rows:
        is_active = row["is_active"]
        is_revoked = row["is_revoked"]
        revoked_by = row["revoked_by"]
        revoke_reason = row["revoke_reason"]
        assert not bool(is_active)
        assert bool(is_revoked)
        assert revoked_by == int(user_id)
        assert revoke_reason == "bulk-logout"
