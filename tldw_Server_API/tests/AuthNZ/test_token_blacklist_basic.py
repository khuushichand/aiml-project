import asyncio
from datetime import datetime, timedelta
import uuid
import pytest

from tldw_Server_API.app.core.AuthNZ.token_blacklist import get_token_blacklist, reset_token_blacklist
from tldw_Server_API.app.core.AuthNZ.settings import reset_settings


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
    assert jti in bl._local_cache

    await asyncio.sleep(0.5)

    # Should drop from cache and return False once expired
    assert await bl.is_blacklisted(jti) is False
    assert jti not in bl._local_cache


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

    async with db_pool.transaction() as conn:
        await conn.execute(
            """
            INSERT INTO sessions (
                user_id, access_jti, refresh_jti, expires_at, refresh_expires_at,
                is_active, is_revoked
            )
            VALUES (?, ?, ?, ?, ?, 1, 0)
            """,
            (
                user_id,
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
