from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.AuthNZ.rate_limiter import RateLimiter


class _StubConn:
    def __init__(self):
        self.queries = []

    async def execute(self, sql, *params):
        self.queries.append(sql)


class _StubTransaction:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _StubPool:
    def __init__(self):
        self.pool = object()  # Truthy sentinel signalling PostgreSQL backend
        self._conn = _StubConn()

    def transaction(self):
        return _StubTransaction(self._conn)

    @property
    def conn(self):
        return self._conn


@pytest.mark.asyncio
async def test_rate_limiter_bootstraps_postgres_schema():
    settings = SimpleNamespace(
        RATE_LIMIT_ENABLED=True,
        RATE_LIMIT_PER_MINUTE=60,
        RATE_LIMIT_BURST=10,
        SERVICE_ACCOUNT_RATE_LIMIT=60,
        REDIS_URL=None,
    )
    pool = _StubPool()
    limiter = RateLimiter(db_pool=pool, settings=settings)

    await limiter.initialize()

    ddl_blob = "\n".join(pool.conn.queries)
    assert "CREATE TABLE IF NOT EXISTS rate_limits" in ddl_blob
    assert "CREATE TABLE IF NOT EXISTS failed_attempts" in ddl_blob
    assert "CREATE TABLE IF NOT EXISTS account_lockouts" in ddl_blob
