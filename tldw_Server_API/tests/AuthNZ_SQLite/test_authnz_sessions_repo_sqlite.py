from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_authnz_sessions_repo_basic_crud_sqlite(tmp_path, monkeypatch):
    """AuthnzSessionsRepo should handle basic create/revoke/list/cleanup on SQLite."""
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool, get_db_pool
    from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables
    from tldw_Server_API.app.core.AuthNZ.repos.sessions_repo import AuthnzSessionsRepo

    db_path = tmp_path / "users.db"
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    reset_settings()
    await reset_db_pool()

    pool = await get_db_pool()
    ensure_authnz_tables(Path(pool.db_path))

    # Ensure sessions table has last_activity column for ordering
    session_columns = await pool.fetchall("PRAGMA table_info(sessions)")
    column_names = {
        row["name"] if isinstance(row, dict) else row[1]
        for row in session_columns or []
    }
    if "last_activity" not in column_names:
        async with pool.transaction() as conn:
            await conn.execute(
                "ALTER TABLE sessions ADD COLUMN last_activity TIMESTAMP"
            )

    # Seed a user row for FK
    async with pool.transaction() as conn:
        await conn.execute(
            """
            INSERT INTO users (username, email, password_hash, is_active)
            VALUES (?, ?, ?, 1)
            """,
            ("alice", "alice@example.com", "x"),
        )

    user_id = await pool.fetchval(
        "SELECT id FROM users WHERE username = ?", ("alice",)
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
        "SELECT is_active, is_revoked FROM sessions WHERE id = ?",
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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, NULL)
            """,
            (
                int(user_id),
                "hash-old",
                "hash-refresh-old",
                "enc-old",
                "enc-refresh-old",
                (now - timedelta(days=2)).isoformat(),
                (now - timedelta(days=1)).isoformat(),
                "127.0.0.1",
                "pytest-old",
                "device-old",
                "access-old",
                "refresh-old",
            ),
        )

    before_count = await pool.fetchval("SELECT COUNT(*) FROM sessions")
    deleted = await repo.cleanup_expired_sessions()
    after_count = await pool.fetchval("SELECT COUNT(*) FROM sessions")

    assert deleted >= 1
    assert after_count == before_count - deleted
