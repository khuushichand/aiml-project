import uuid
import pytest
from datetime import datetime, timedelta


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_session_cleanup_removes_expired(test_db_pool):
    from tldw_Server_API.app.core.AuthNZ.session_manager import SessionManager

    pool = test_db_pool
    # Use a SessionManager bound explicitly to the Postgres pool
    session_manager = SessionManager(db_pool=pool)
    await session_manager.initialize()

    # Insert a test user
    user_uuid = uuid.uuid4()
    user_id = await pool.fetchval(
        """
        INSERT INTO users (uuid, username, email, password_hash, is_active)
        VALUES ($1, $2, $3, $4, TRUE)
        RETURNING id
        """,
        user_uuid,
        "cleanup_user",
        "cleanup@example.com",
        "hash",
    )

    expired_at = datetime.utcnow() - timedelta(days=2)
    revoked_at = datetime.utcnow() - timedelta(days=8)
    active_at = datetime.utcnow() + timedelta(days=2)

    expired_session_id = await pool.fetchval(
        """
        INSERT INTO sessions (
            user_id, token_hash, refresh_token_hash, expires_at,
            is_active, revoked_at
        )
        VALUES ($1, $2, $3, $4, TRUE, NULL)
        RETURNING id
        """,
        user_id,
        "expired_access",
        "expired_refresh",
        expired_at,
    )

    revoked_session_id = await pool.fetchval(
        """
        INSERT INTO sessions (
            user_id, token_hash, refresh_token_hash, expires_at,
            is_active, revoked_at
        )
        VALUES ($1, $2, $3, $4, FALSE, $5)
        RETURNING id
        """,
        user_id,
        "revoked_access",
        "revoked_refresh",
        active_at,
        revoked_at,
    )

    active_session_id = await pool.fetchval(
        """
        INSERT INTO sessions (
            user_id, token_hash, refresh_token_hash, expires_at,
            is_active, revoked_at
        )
        VALUES ($1, $2, $3, $4, TRUE, NULL)
        RETURNING id
        """,
        user_id,
        "active_access",
        "active_refresh",
        active_at,
    )

    # Run cleanup (should not raise despite previous SQL bug)
    await session_manager.cleanup_expired_sessions()

    # Expired and long-revoked sessions should be removed
    expired_count = await pool.fetchval(
        "SELECT COUNT(*) FROM sessions WHERE id = $1", expired_session_id
    )
    revoked_count = await pool.fetchval(
        "SELECT COUNT(*) FROM sessions WHERE id = $1", revoked_session_id
    )
    active_count = await pool.fetchval(
        "SELECT COUNT(*) FROM sessions WHERE id = $1", active_session_id
    )

    assert expired_count == 0
    assert revoked_count == 0
    assert active_count == 1
