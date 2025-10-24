from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from contextlib import asynccontextmanager

import pytest
from redis.exceptions import RedisError

from tldw_Server_API.app.core.AuthNZ.token_blacklist import TokenBlacklist


class _FakeConn:
    def __init__(self):
        self.rows = {}
        self._pending_row = None

    async def execute(self, query, *args):
        normalized_query = " ".join(query.split())
        if "INSERT" in normalized_query and "token_blacklist" in normalized_query:
            params = args
            if len(args) == 1 and isinstance(args[0], (tuple, list)):
                params = args[0]
            jti = params[0]
            user_id = params[1]
            token_type = params[2]
            expires_at = params[3]
            self.rows[jti] = {
                "user_id": user_id,
                "token_type": token_type,
                "expires_at": expires_at,
            }
            return self
        if "SELECT expires_at" in normalized_query and "token_blacklist" in normalized_query:
            params = args
            if len(args) == 1 and isinstance(args[0], (tuple, list)):
                params = args[0]
            jti = params[0]
            current_time = params[1]
            record = self.rows.get(jti)
            if not record:
                self._pending_row = None
                return self
            expires_at = record["expires_at"]
            if isinstance(expires_at, str):
                expires_dt = datetime.fromisoformat(expires_at)
            else:
                expires_dt = expires_at
            if isinstance(current_time, str):
                current_dt = datetime.fromisoformat(current_time)
            else:
                current_dt = current_time
            if expires_dt > current_dt:
                self._pending_row = (record["expires_at"],)
            else:
                self._pending_row = None
            return self
        return self

    async def fetchval(self, query, jti, current_time):
        if isinstance(jti, (tuple, list)):
            jti, current_time = jti
        record = self.rows.get(jti)
        if not record:
            return False
        expires_at = record["expires_at"]
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        return expires_at > current_time

    async def fetchone(self):
        result = self._pending_row
        self._pending_row = None
        return result

    async def commit(self):
        return None


class _FakePool:
    def __init__(self):
        self.conn = _FakeConn()
        self.pool = None
        self._initialized = True

    async def initialize(self):
        self._initialized = True

    @asynccontextmanager
    async def transaction(self):
        yield self.conn

    @asynccontextmanager
    async def acquire(self):
        yield self.conn


@pytest.mark.asyncio
async def test_token_blacklist_falls_back_to_database(monkeypatch):
    settings = SimpleNamespace(REDIS_URL="redis://localhost:6379/0", PII_REDACT_LOGS=False)
    pool = _FakePool()

    def failing_from_url(*_args, **_kwargs):
        raise RedisError("connection failed")

    monkeypatch.setattr(
        "tldw_Server_API.app.core.AuthNZ.token_blacklist.redis_async.from_url",
        failing_from_url,
    )

    blacklist = TokenBlacklist(settings=settings, db_pool=pool)
    await blacklist.initialize()

    class FailingRedisClient:
        async def setex(self, *args, **kwargs):
            raise RedisError("setex failed")

        async def exists(self, *args, **kwargs):
            raise RedisError("exists failed")

        async def close(self):
            return None

    blacklist.redis_client = FailingRedisClient()

    jti = "unit-test-jti"
    expires_at = datetime.utcnow() + timedelta(minutes=30)

    assert await blacklist.revoke_token(
        jti,
        expires_at,
        user_id=42,
        token_type="access",
        reason="unit-test",
    )

    blacklist._local_cache.clear()

    assert await blacklist.is_blacklisted(jti) is True
    stored = pool.conn.rows.get(jti)
    assert stored["user_id"] == 42
    assert stored["token_type"] == "access"


@pytest.mark.asyncio
async def test_token_blacklist_normalizes_sqlite_expiry(monkeypatch):
    settings = SimpleNamespace(REDIS_URL=None, PII_REDACT_LOGS=False)
    pool = _FakePool()

    blacklist = TokenBlacklist(settings=settings, db_pool=pool)
    await blacklist.initialize()

    future_utc = (datetime.now(timezone.utc) + timedelta(hours=1)).replace(microsecond=0)
    offset_expiry = future_utc.astimezone(timezone(timedelta(hours=-5)))

    await blacklist.revoke_token(
        jti="tz-jti",
        expires_at=offset_expiry,
        user_id=7,
        token_type="refresh",
        reason="timezone-test",
    )

    stored = pool.conn.rows["tz-jti"]
    assert isinstance(stored["expires_at"], str)
    assert stored["expires_at"] == future_utc.replace(tzinfo=None).isoformat()

    # Clear cache to exercise DB comparison logic using normalized timestamps
    blacklist._local_cache.clear()
    assert await blacklist.is_blacklisted("tz-jti") is True
