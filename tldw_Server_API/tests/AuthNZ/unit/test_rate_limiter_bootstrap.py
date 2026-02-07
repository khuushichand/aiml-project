from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.AuthNZ.exceptions import RateLimitError
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


@pytest.mark.asyncio
async def test_rate_limiter_legacy_rate_checks_are_intentional_noops():
    settings = SimpleNamespace(
        RATE_LIMIT_ENABLED=True,
        RATE_LIMIT_PER_MINUTE=60,
        RATE_LIMIT_BURST=10,
        SERVICE_ACCOUNT_RATE_LIMIT=60,
        REDIS_URL=None,
    )
    limiter = RateLimiter(db_pool=None, settings=settings)

    ip_allowed, ip_meta = await limiter.check_rate_limit(
        identifier="ip:127.0.0.1",
        endpoint="/api/v1/auth/login",
        limit=1,
        window_minutes=1,
    )
    user_allowed, user_meta = await limiter.check_user_rate_limit(
        user_id=42,
        endpoint="/api/v1/chat/completions",
        limit=1,
        window_minutes=1,
    )

    assert ip_allowed is True
    assert user_allowed is True
    assert ip_meta.get("rate_limit_source") == "resource_governor"
    assert user_meta.get("rate_limit_source") == "resource_governor"


@pytest.mark.asyncio
async def test_rate_limiter_fallback_enforces_limit():
    settings = SimpleNamespace(
        RATE_LIMIT_ENABLED=True,
        RATE_LIMIT_PER_MINUTE=60,
        RATE_LIMIT_BURST=10,
        SERVICE_ACCOUNT_RATE_LIMIT=60,
        REDIS_URL=None,
    )
    limiter = RateLimiter(db_pool=object(), settings=settings)
    limiter._initialized = True

    class _Repo:
        async def increment_rate_limit_window(self, *, identifier, endpoint, window_start):
            return 2

    limiter._get_rate_limits_repo = lambda: _Repo()  # type: ignore[method-assign]

    allowed, meta = await limiter.check_rate_limit_fallback(
        identifier="ip:203.0.113.11",
        endpoint="auth:authnz.forgot_password",
        limit=1,
        window_minutes=1,
        fail_open=False,
    )
    assert allowed is False
    assert meta.get("rate_limit_source") == "authnz_fallback_db"
    assert int(meta.get("retry_after", 0)) >= 1


@pytest.mark.asyncio
async def test_rate_limiter_fallback_can_fail_open_on_backend_error():
    settings = SimpleNamespace(
        RATE_LIMIT_ENABLED=True,
        RATE_LIMIT_PER_MINUTE=60,
        RATE_LIMIT_BURST=10,
        SERVICE_ACCOUNT_RATE_LIMIT=60,
        REDIS_URL=None,
    )
    limiter = RateLimiter(db_pool=object(), settings=settings)
    limiter._initialized = True

    class _Repo:
        async def increment_rate_limit_window(self, *, identifier, endpoint, window_start):
            raise RuntimeError("db unavailable")

    limiter._get_rate_limits_repo = lambda: _Repo()  # type: ignore[method-assign]

    allowed, meta = await limiter.check_rate_limit_fallback(
        identifier="ip:203.0.113.12",
        endpoint="auth:authnz.magic_link.request",
        limit=10,
        window_minutes=1,
        fail_open=True,
    )
    assert allowed is True
    assert meta.get("error") == "fallback_limiter_unavailable"


@pytest.mark.asyncio
async def test_rate_limiter_fallback_can_fail_closed_on_backend_error():
    settings = SimpleNamespace(
        RATE_LIMIT_ENABLED=True,
        RATE_LIMIT_PER_MINUTE=60,
        RATE_LIMIT_BURST=10,
        SERVICE_ACCOUNT_RATE_LIMIT=60,
        REDIS_URL=None,
    )
    limiter = RateLimiter(db_pool=object(), settings=settings)
    limiter._initialized = True

    class _Repo:
        async def increment_rate_limit_window(self, *, identifier, endpoint, window_start):
            raise RuntimeError("db unavailable")

    limiter._get_rate_limits_repo = lambda: _Repo()  # type: ignore[method-assign]

    with pytest.raises(RateLimitError):
        await limiter.check_rate_limit_fallback(
            identifier="ip:203.0.113.13",
            endpoint="auth:authnz.magic_link.email",
            limit=3,
            window_minutes=10,
            fail_open=False,
        )
