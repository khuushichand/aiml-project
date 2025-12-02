from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

import pytest

pytest_plugins = ("tldw_Server_API.tests.AuthNZ.conftest",)


@pytest.mark.asyncio
async def test_authnz_sessions_repo_basic_crud_sqlite(isolated_test_environment):
    """AuthnzSessionsRepo should handle basic create/revoke/list/cleanup."""
    _client, _db_name = isolated_test_environment
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
    from tldw_Server_API.app.core.AuthNZ.repos.sessions_repo import AuthnzSessionsRepo

    pool = await get_db_pool()

    # Seed a user row for FK
    async with pool.transaction() as conn:
        user_id = await conn.fetchval(
            """
            INSERT INTO users (username, email, password_hash, is_active, is_verified, uuid)
            VALUES ($1, $2, $3, TRUE, TRUE, $4)
            RETURNING id
            """,
            "alice",
            "alice@example.com",
            "x",
            uuid.uuid4(),
        )

    assert user_id is not None

    repo = AuthnzSessionsRepo(pool)

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=1)
    refresh_expires = now + timedelta(days=7)

    # Create a session record
    session_id = await repo.create_session_record(
        user_id=int(user_id),
        token_hash="hash-access",
        refresh_token_hash="hash-refresh",
        encrypted_token="enc-access",
        encrypted_refresh="enc-refresh",
        expires_at=expires_at,
        refresh_expires_at=refresh_expires,
        ip_address="127.0.0.1",
        user_agent="pytest",
        device_id="device-1",
        access_jti="access-jti",
        refresh_jti="refresh-jti",
    )
    assert session_id > 0

    # get_active_sessions_for_user should see the session
    sessions = await repo.get_active_sessions_for_user(int(user_id))
    assert any(s["id"] == session_id for s in sessions)

    # Revoke the session and ensure repo returns details suitable for blacklist
    details = await repo.revoke_session_record(
        session_id=session_id,
        revoked_by=int(user_id),
        reason="unit-test",
    )
    assert details is not None
    assert details["id"] == session_id
    assert details["user_id"] == int(user_id)

    row = await pool.fetchone(
        "SELECT is_active, is_revoked FROM sessions WHERE id = $1",
        session_id,
    )
    assert row is not None
    is_active = row["is_active"] if isinstance(row, dict) else row[0]
    is_revoked = row["is_revoked"] if isinstance(row, dict) else row[1]
    assert not bool(is_active)
    assert bool(is_revoked)

    # Cleanup logic should delete old sessions but keep recent ones
    # Insert an expired session manually
    async with pool.transaction() as conn:
        await conn.execute(
            """
            INSERT INTO sessions (
                user_id, token_hash, refresh_token_hash,
                encrypted_token, encrypted_refresh,
                expires_at, refresh_expires_at,
                ip_address, user_agent, device_id,
                access_jti, refresh_jti,
                is_active, is_revoked, revoked_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, FALSE, FALSE, NULL)
            """,
            int(user_id),
            "hash-old",
            "hash-refresh-old",
            "enc-old",
            "enc-refresh-old",
            (now - timedelta(days=2)),
            (now - timedelta(days=1)),
            "127.0.0.1",
            "pytest-old",
            "device-old",
            "access-old",
            "refresh-old",
        )

    before_count = await pool.fetchval("SELECT COUNT(*) FROM sessions")
    deleted = await repo.cleanup_expired_sessions()
    after_count = await pool.fetchval("SELECT COUNT(*) FROM sessions")

    assert deleted >= 1
    assert after_count == before_count - deleted


@pytest.mark.asyncio
async def test_authnz_sessions_repo_validation_and_refresh_sqlite(
    isolated_test_environment,
):
    """AuthnzSessionsRepo validation/refresh helpers should behave on SQLite."""
    _client, _db_name = isolated_test_environment
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
    from tldw_Server_API.app.core.AuthNZ.repos.sessions_repo import AuthnzSessionsRepo

    pool = await get_db_pool()

    # Seed a user row for FK
    async with pool.transaction() as conn:
        user_id = await conn.fetchval(
            """
            INSERT INTO users (username, email, password_hash, is_active, is_verified, uuid)
            VALUES ($1, $2, $3, TRUE, TRUE, $4)
            RETURNING id
            """,
            "bob",
            "bob@example.com",
            "x",
            uuid.uuid4(),
        )

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
        user_agent="pytest",
        device_id="device-2",
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

    row = await pool.fetchone(
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
async def test_authnz_sessions_repo_bulk_revocation_sqlite(isolated_test_environment):
    """AuthnzSessionsRepo bulk revocation helpers should behave on SQLite."""
    _client, _db_name = isolated_test_environment
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
    from tldw_Server_API.app.core.AuthNZ.repos.sessions_repo import AuthnzSessionsRepo

    pool = await get_db_pool()

    # Seed a user row for FK
    async with pool.transaction() as conn:
        user_id = await conn.fetchval(
            """
            INSERT INTO users (username, email, password_hash, is_active, is_verified, uuid)
            VALUES ($1, $2, $3, TRUE, TRUE, $4)
            RETURNING id
            """,
            "carol",
            "carol@example.com",
            "x",
            uuid.uuid4(),
        )

    repo = AuthnzSessionsRepo(pool)

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=1)
    refresh_expires = now + timedelta(days=7)

    # Create a couple of active sessions with JTIs
    for idx in range(2):
        await repo.create_session_record(
            user_id=int(user_id),
            token_hash=f"hash-access-{idx}",
            refresh_token_hash=f"hash-refresh-{idx}",
            encrypted_token=f"enc-access-{idx}",
            encrypted_refresh=f"enc-refresh-{idx}",
            expires_at=expires_at,
            refresh_expires_at=refresh_expires,
            ip_address="127.0.0.1",
            user_agent=f"pytest-{idx}",
            device_id=f"device-{idx}",
            access_jti=f"access-jti-{idx}",
            refresh_jti=f"refresh-jti-{idx}",
        )

    # Fetch token metadata snapshot
    sessions = await repo.fetch_session_token_metadata_for_user(int(user_id))
    assert len(sessions) >= 2
    for entry in sessions:
        assert "id" in entry
        assert "access_jti" in entry
        assert "refresh_jti" in entry

    # Mark all sessions as revoked with audit metadata
    affected = await repo.mark_sessions_revoked_for_user_with_audit(
        user_id=int(user_id),
        revoked_by=int(user_id),
        reason="bulk-logout",
    )
    assert affected >= 2

    rows = await pool.fetchall(
        """
        SELECT is_active, is_revoked, revoked_by, revoke_reason
        FROM sessions
        WHERE user_id = $1
        """,
        int(user_id),
    )
    assert rows
    for row in rows:
        if isinstance(row, dict):
            is_active = row["is_active"]
            is_revoked = row["is_revoked"]
            revoked_by = row["revoked_by"]
            revoke_reason = row["revoke_reason"]
        else:
            is_active = row[0]
            is_revoked = row[1]
            revoked_by = row[2]
            revoke_reason = row[3]
        assert not bool(is_active)
        assert bool(is_revoked)
        assert revoked_by == int(user_id)
        assert revoke_reason == "bulk-logout"
