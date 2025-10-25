import pytest

from tldw_Server_API.app.core.AuthNZ.settings import Settings
from tldw_Server_API.app.core.AuthNZ.database import DatabasePool
from tldw_Server_API.app.core.AuthNZ.rate_limiter import RateLimiter


@pytest.mark.asyncio
async def test_sqlite_get_current_usage_returns_inserted_count(tmp_path):
    # Configure a SQLite database and initialize RateLimiter
    db_path = tmp_path / "authnz_rate_limit.db"
    settings = Settings(
        AUTH_MODE="multi_user",
        JWT_SECRET_KEY="x" * 64,
        DATABASE_URL=f"sqlite:///{db_path}",
        RATE_LIMIT_ENABLED=True,
        RATE_LIMIT_PER_MINUTE=100,
        RATE_LIMIT_BURST=10,
        SERVICE_ACCOUNT_RATE_LIMIT=100,
    )
    db_pool = DatabasePool(settings)
    await db_pool.initialize()

    limiter = RateLimiter(db_pool=db_pool, settings=settings)
    await limiter.initialize()
    limiter.redis_client = None

    identifier = "user:sqlite"
    endpoint = "/api/sqlite-usage"

    # First request creates a record in current window (SQLite stores window_start as TEXT ISO)
    allowed, _ = await limiter.check_rate_limit(
        identifier=identifier, endpoint=endpoint, limit=5, burst=0, window_minutes=1
    )
    assert allowed is True

    # get_current_usage should return current_count = 1 (and not error due to datetime param typing)
    usage = await limiter.get_current_usage(identifier, endpoint)
    assert isinstance(usage, dict)
    assert usage.get("current_count") == 1

    # Cleanup
    await db_pool.close()
