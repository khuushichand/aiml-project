import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from contextlib import asynccontextmanager

from redis.exceptions import RedisError

from tldw_Server_API.app.core.AuthNZ.token_blacklist import TokenBlacklist


class _FakeConn:
    def __init__(self):
        self.rows = {}

    async def execute(self, query, *args):
        if "INSERT INTO token_blacklist" in query:
            jti = args[0]
            user_id = args[1]
            token_type = args[2]
            expires_at = args[3]
            self.rows[jti] = {
                "user_id": user_id,
                "token_type": token_type,
                "expires_at": expires_at,
            }

    async def fetchval(self, query, jti, current_time):
        record = self.rows.get(jti)
        if not record:
            return False
        expires_at = record["expires_at"]
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        return expires_at > current_time


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


def test_token_blacklist_falls_back_to_database(monkeypatch):
    async def _run():
        settings = SimpleNamespace(REDIS_URL="redis://localhost:6379/0")
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

    asyncio.run(_run())
