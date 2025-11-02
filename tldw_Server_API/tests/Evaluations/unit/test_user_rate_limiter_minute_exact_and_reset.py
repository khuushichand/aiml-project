import time
from datetime import datetime, timezone

import pytest

from tldw_Server_API.app.core.Evaluations.user_rate_limiter import (
    UserRateLimiter,
    UserTier,
)


@pytest.mark.unit
def test_minute_limit_exact_endpoint_and_reset_header(tmp_path):
    db_path = tmp_path / "evals_rate_limit.db"
    limiter = UserRateLimiter(db_path=str(db_path))

    user_id = "u-eval"
    endpoint = "/api/evals/run"

    # Configure strict per-minute limit to 1, burst 0 for deterministic behavior
    # Keep reasonable daily limits
    import asyncio

    async def _upgrade():
        await limiter.upgrade_user_tier(
            user_id=user_id,
            new_tier=UserTier.CUSTOM,
            custom_limits={
                "evaluations_per_minute": 1,
                "batch_evaluations_per_minute": 1,
                "evaluations_per_day": 100,
                "total_tokens_per_day": 100000,
                "burst_size": 0,
                "max_cost_per_day": 10.0,
                "max_cost_per_month": 100.0,
            },
        )

    asyncio.run(_upgrade())

    # Insert a conflicting record with a different endpoint that shares a prefix
    now = datetime.now(timezone.utc)
    with __import__("sqlite3").connect(str(db_path)) as conn:
        conn.execute(
            "INSERT INTO rate_limit_tracking (user_id, endpoint, timestamp, tokens_used, cost) VALUES (?, ?, ?, ?, ?)",
            (user_id, f"{endpoint}/extra", now.isoformat(), 0, 0.0),
        )
        conn.commit()

    # First call should be allowed because we use exact endpoint matching now
    async def _first():
        ok, meta = await limiter.check_rate_limit(
            user_id=user_id, endpoint=endpoint, is_batch=False, tokens_requested=0, estimated_cost=0.0
        )
        assert ok is True
        headers = meta.get("headers", {})
        reset_epoch = int(headers.get("X-RateLimit-Reset", 0))
        # Reset is within the current minute
        assert reset_epoch > int(time.time())
        assert reset_epoch <= int(time.time()) + 60

    asyncio.run(_first())
