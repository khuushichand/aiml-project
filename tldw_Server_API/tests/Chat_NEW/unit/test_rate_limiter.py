import asyncio

import pytest

from tldw_Server_API.app.core.Chat.rate_limiter import TokenBucket


@pytest.mark.asyncio
async def test_token_bucket_concurrent_consume_does_not_over_consume():
    capacity = 5
    bucket = TokenBucket(capacity=capacity, refill_rate=capacity / 60.0)

    async def worker():
        return await bucket.consume(1)

    results = await asyncio.gather(*(worker() for _ in range(10)))

    successes = sum(1 for r in results if r)
    failures = len(results) - successes

    # At most `capacity` workers should be allowed to consume a token.
    assert successes <= capacity
    # Under concurrent load, we expect some workers to fail.
    assert failures >= 1
