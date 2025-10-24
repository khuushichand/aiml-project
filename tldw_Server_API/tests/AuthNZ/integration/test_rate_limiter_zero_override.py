import pytest

from tldw_Server_API.app.core.AuthNZ.database import DatabasePool
from tldw_Server_API.app.core.AuthNZ.settings import Settings
from tldw_Server_API.app.core.AuthNZ.rate_limiter import RateLimiter


pytestmark = pytest.mark.integration

@pytest.mark.asyncio
async def test_rate_limiter_zero_limit_is_unbounded():
    settings = Settings(
        AUTH_MODE="multi_user",
        JWT_SECRET_KEY="z" * 64,
        DATABASE_URL="sqlite:///:memory:",
        RATE_LIMIT_ENABLED=True,
    )
    limiter = RateLimiter(settings=settings)
    limiter.redis_client = None
    limiter._initialized = True

    allowed, meta = await limiter.check_rate_limit(
        identifier="user-0", endpoint="/api/test", limit=0, burst=0, window_minutes=2
    )

    assert allowed is True
    assert meta["limit"] == 0
    assert meta["unbounded"] is True
    assert meta.get("rate_limit_enabled", True) is True
    assert meta.get("remaining") is None
    assert meta.get("reset_time") is None
    assert meta.get("retry_after") is None


@pytest.mark.asyncio
async def test_rate_limiter_hits_database_for_positive_limit(tmp_path):
    db_path = tmp_path / "rate_limit.db"
    settings = Settings(
        AUTH_MODE="multi_user",
        JWT_SECRET_KEY="y" * 64,
        DATABASE_URL=f"sqlite:///{db_path}",
        RATE_LIMIT_ENABLED=True,
    )
    db_pool = DatabasePool(settings)
    await db_pool.initialize()
    try:
        limiter = RateLimiter(settings=settings, db_pool=db_pool)
        limiter.redis_client = None
        limiter._initialized = True

        allowed, meta = await limiter.check_rate_limit(
            identifier="user-positive",
            endpoint="/api/limited",
            limit=1,
            burst=0,
            window_minutes=1,
        )
        assert allowed is True
        assert meta["limit"] == 1

        allowed_second, meta_second = await limiter.check_rate_limit(
            identifier="user-positive",
            endpoint="/api/limited",
            limit=1,
            burst=0,
            window_minutes=1,
        )
        assert allowed_second is False
        assert meta_second["limit"] == 1
        assert meta_second["retry_after"] >= 0
    finally:
        await db_pool.close()
