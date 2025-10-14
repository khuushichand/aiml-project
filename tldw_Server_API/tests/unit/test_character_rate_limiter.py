import asyncio
import pytest

from tldw_Server_API.app.core.Character_Chat.character_rate_limiter import CharacterRateLimiter


@pytest.mark.unit
def test_rate_limiter_memory_fallback_allows_operations_without_redis():
    limiter = CharacterRateLimiter(redis_client=None, max_operations=3, window_seconds=60)

    async def run_checks():
        ok1, rem1 = await limiter.check_rate_limit(user_id=123, operation="test")
        ok2, rem2 = await limiter.check_rate_limit(user_id=123, operation="test")
        ok3, rem3 = await limiter.check_rate_limit(user_id=123, operation="test")
        assert ok1 and ok2 and ok3
        assert rem1 == 2 and rem2 == 1 and rem3 == 0

    asyncio.run(run_checks())


@pytest.mark.unit
def test_rate_limiter_per_minute_specific_operation_limits():
    limiter = CharacterRateLimiter(redis_client=None, max_message_sends_per_minute=2)

    async def run_checks():
        ok1, rem1 = await limiter.check_message_send_rate(user_id=999)
        ok2, rem2 = await limiter.check_message_send_rate(user_id=999)
        assert ok1 and ok2
        assert rem1 == 1 and rem2 == 0
        with pytest.raises(Exception):
            await limiter.check_message_send_rate(user_id=999)

    asyncio.run(run_checks())

