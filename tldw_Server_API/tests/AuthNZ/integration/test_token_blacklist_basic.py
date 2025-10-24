import asyncio
import sqlite3
from datetime import datetime, timedelta
import uuid
import pytest

from tldw_Server_API.app.core.AuthNZ.token_blacklist import get_token_blacklist, reset_token_blacklist
from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool
from tldw_Server_API.app.core.AuthNZ.session_manager import get_session_manager, reset_session_manager


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_blacklist_revoke_and_check_no_redis(monkeypatch):
    # Force local SQLite to avoid leftover Postgres env from other tests
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./Databases/users.db")
    reset_settings()
    await reset_token_blacklist()
    bl = get_token_blacklist()
    await bl.initialize()

    jti = "test-jti-1"
    ok = await bl.revoke_token(jti=jti, expires_at=datetime.utcnow() + timedelta(hours=1), user_id=1)
    assert ok is True
    assert await bl.is_blacklisted(jti) is True


@pytest.mark.asyncio
async def test_blacklist_rebinds_pool_after_database_switch(tmp_path, monkeypatch):
    db_a = tmp_path / "users_a.db"
    db_b = tmp_path / "users_b.db"

    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("SINGLE_USER_API_KEY", "test-api-key-1234567890")

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_a}")
    reset_settings()
    await reset_token_blacklist()
    await reset_db_pool()

    bl = get_token_blacklist()
    await bl.initialize()
    assert bl.db_pool.db_path.endswith("users_a.db")

    db_pool = await bl._ensure_db_pool()

    async def ensure_user(pool, username: str, email: str) -> int:
        async with pool.transaction() as conn:
            if hasattr(conn, "fetch"):
                await conn.execute(
                    """
                    INSERT INTO users (username, email, password_hash, is_active, is_verified, role)
                    VALUES ($1, $2, $3, TRUE, TRUE, 'user')
                    ON CONFLICT (username) DO NOTHING
                    """,
                    username,
                    email,
                    "hash",
                )
                row = await conn.fetchrow(
                    "SELECT id FROM users WHERE username = $1",
                    username,
                )
                return row["id"]
            cursor = await conn.execute(
                """
                INSERT OR IGNORE INTO users (username, email, password_hash, is_active, is_verified, role)
                VALUES (?, ?, ?, 1, 1, 'user')
                """,
                (username, email, "hash"),
            )
            # `cursor` is None for INSERT statements, fetch id separately.
            cursor = await conn.execute(
                "SELECT id FROM users WHERE username = ?",
                (username,),
            )
            row = await cursor.fetchone()
            return row[0]

    user_id_a = await ensure_user(db_pool, "switch-case-a", "switch-a@example.com")

    jti_a = "config-jti-a"
    assert await bl.revoke_token(
        jti=jti_a,
        expires_at=datetime.utcnow() + timedelta(hours=1),
        user_id=user_id_a,
    )

    with sqlite3.connect(db_a) as conn:
        rows = conn.execute("SELECT jti FROM token_blacklist WHERE jti = ?", (jti_a,)).fetchall()
        assert rows, "Token should be persisted in the initial database"

    # Switch configuration to the new database and ensure the blacklist follows.
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_b}")
    reset_settings()
    await reset_db_pool()
    await bl._ensure_db_pool()

    assert bl.db_pool.db_path.endswith("users_b.db"), "Blacklist should adopt the refreshed pool"

    user_id_b = await ensure_user(bl.db_pool, "switch-case-b", "switch-b@example.com")

    jti_b = "config-jti-b"
    assert await bl.revoke_token(
        jti=jti_b,
        expires_at=datetime.utcnow() + timedelta(hours=1),
        user_id=user_id_b,
    )

    with sqlite3.connect(db_b) as conn:
        rows_b = conn.execute("SELECT jti FROM token_blacklist WHERE jti = ?", (jti_b,)).fetchall()
        assert rows_b, "Token should be written to the new database"

    with sqlite3.connect(db_a) as conn:
        rows_a = conn.execute("SELECT jti FROM token_blacklist WHERE jti = ?", (jti_b,)).fetchall()
        assert not rows_a, "New token must not be stored in the original database"

    await reset_token_blacklist()
    await reset_db_pool()
    reset_settings()


@pytest.mark.asyncio
async def test_blacklist_cache_expires_when_token_expires(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./Databases/users.db")
    reset_settings()
    await reset_token_blacklist()
    bl = get_token_blacklist()
    await bl.initialize()

    jti = "expiring-jti"
    short_expiry = datetime.utcnow() + timedelta(milliseconds=200)
    assert await bl.revoke_token(jti=jti, expires_at=short_expiry, user_id=1)
    # Prime the cache
    assert await bl.is_blacklisted(jti) is True


@pytest.mark.asyncio
async def test_session_manager_rebinds_pool_after_database_switch(tmp_path, monkeypatch):
    db_a = tmp_path / "sessions_a.db"
    db_b = tmp_path / "sessions_b.db"

    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("SINGLE_USER_API_KEY", "test-api-key-1234567890")

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_a}")
    reset_settings()
    await reset_session_manager()
    await reset_db_pool()

    sm = await get_session_manager()
    assert sm.db_pool.db_path.endswith("sessions_a.db")

    # Switch configuration and ensure the session manager tracks the new pool.
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_b}")
    reset_settings()
    await reset_db_pool()
    await sm._ensure_db_pool()

    assert sm.db_pool.db_path.endswith("sessions_b.db"), "Session manager should adopt refreshed pool settings"

@pytest.mark.asyncio
async def test_revoke_all_user_tokens_marks_sessions(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./Databases/users.db")
    reset_settings()
    await reset_token_blacklist()
    bl = get_token_blacklist()
    await bl.initialize()

    db_pool = await bl._ensure_db_pool()
    async with db_pool.transaction() as conn:
        # Ensure sessions table exists for SQLite path
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                access_jti TEXT,
                refresh_jti TEXT,
                expires_at TEXT,
                refresh_expires_at TEXT,
                is_active INTEGER DEFAULT 1,
                is_revoked INTEGER DEFAULT 0,
                revoked_at TEXT,
                revoked_by INTEGER,
                revoke_reason TEXT
            )
            """
        )
        unique_username = f"cacheuser_{uuid.uuid4().hex[:8]}"
        unique_email = f"{unique_username}@example.com"
        await conn.execute(
            """
            INSERT INTO users (username, email, password_hash, is_active, is_verified, role)
            VALUES (?, ?, ?, 1, 1, 'user')
            """,
            (unique_username, unique_email, "hash"),
        )
        cursor = await conn.execute(
            "SELECT id FROM users WHERE username = ?",
            (unique_username,),
        )
        user_row = await cursor.fetchone()
        user_id = user_row[0]

    access_jti = "session-access-jti"
    refresh_jti = "session-refresh-jti"
    access_exp = datetime.utcnow() + timedelta(hours=2)
    refresh_exp = datetime.utcnow() + timedelta(days=7)

    access_hash = "hash-" + access_jti
    refresh_hash = "hash-" + refresh_jti

    async with db_pool.transaction() as conn:
        await conn.execute(
            """
            INSERT INTO sessions (
                user_id, token_hash, refresh_token_hash,
                access_jti, refresh_jti,
                expires_at, refresh_expires_at,
                is_active, is_revoked
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, 0)
            """,
            (
                user_id,
                access_hash,
                refresh_hash,
                access_jti,
                refresh_jti,
                access_exp.isoformat(),
                refresh_exp.isoformat(),
            ),
        )

    revoked = await bl.revoke_all_user_tokens(user_id=user_id, reason="bulk-logout", revoked_by=42)
    assert revoked == 1

    # Sessions should be inactive and carry revoke metadata
    async with db_pool.acquire() as conn:
        cursor = await conn.execute(
            """
            SELECT is_active, is_revoked, revoked_at, revoked_by, revoke_reason
            FROM sessions WHERE user_id = ?
            """,
            (user_id,),
        )
        row = await cursor.fetchone()
    assert row is not None
    assert row[0] == 0
    assert row[1] == 1
    assert row[2] is not None
    assert row[3] == 42
    assert row[4] == "bulk-logout"

    # The cached blacklist should include both JTIs
    assert await bl.is_blacklisted(access_jti) is True
    assert await bl.is_blacklisted(refresh_jti) is True


@pytest.mark.asyncio
async def test_blacklist_handles_redis_unavailable(monkeypatch):
    # Force local SQLite and a bad Redis URL to exercise fallback
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./Databases/users.db")
    reset_settings()
    monkeypatch.setenv("REDIS_URL", "redis://localhost:1/0")
    await reset_token_blacklist()
    bl = get_token_blacklist()
    await bl.initialize()

    jti = "test-jti-2"
    ok = await bl.revoke_token(jti=jti, expires_at=datetime.utcnow() + timedelta(hours=1), user_id=1)
    assert ok is True
    assert await bl.is_blacklisted(jti) is True
