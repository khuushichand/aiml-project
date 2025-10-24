import asyncio
import pytest

from fastapi import HTTPException

from tldw_Server_API.app.core.Character_Chat.character_rate_limiter import CharacterRateLimiter
from tldw_Server_API.app.core.config import clear_config_cache, settings


class _FailingPipeline:
    def zremrangebyscore(self, *args, **kwargs):
        return self

    def zcard(self, *args, **kwargs):
        return self

    def zadd(self, *args, **kwargs):
        return self

    def expire(self, *args, **kwargs):
        return self

    def execute(self):
        raise RuntimeError("redis unavailable")


class _FailingRedis:
    def pipeline(self):
        return _FailingPipeline()


class _InMemoryRedisPipeline:
    def __init__(self, store):
        self.store = store
        self.ops = []

    def zremrangebyscore(self, key, min_score, max_score):
        self.ops.append(("zremrange", key, min_score, max_score))
        return self

    def zcard(self, key):
        self.ops.append(("zcard", key))
        return self

    def zadd(self, key, mapping):
        self.ops.append(("zadd", key, mapping))
        return self

    def expire(self, key, seconds):
        self.ops.append(("expire", key, seconds))
        return self

    def execute(self):
        results = []
        for op in self.ops:
            name = op[0]
            if name == "zremrange":
                key, min_score, max_score = op[1], op[2], op[3]
                bucket = self.store.setdefault(key, {})
                to_remove = [member for member, score in bucket.items() if min_score <= score <= max_score]
                for member in to_remove:
                    bucket.pop(member, None)
                results.append(len(to_remove))
            elif name == "zcard":
                key = op[1]
                bucket = self.store.setdefault(key, {})
                results.append(len(bucket))
            elif name == "zadd":
                key, mapping = op[1], op[2]
                bucket = self.store.setdefault(key, {})
                added = 0
                for member, score in mapping.items():
                    if member not in bucket:
                        added += 1
                    bucket[member] = score
                results.append(added)
            elif name == "expire":
                results.append(True)
        self.ops = []
        return results


class _InMemoryRedis:
    def __init__(self):
        self.store = {}

    def pipeline(self):
        return _InMemoryRedisPipeline(self.store)

    def zrem(self, key, member):
        bucket = self.store.get(key)
        if not bucket:
            return 0
        return 1 if bucket.pop(member, None) is not None else 0

    def zremrangebyscore(self, key, min_score, max_score):
        bucket = self.store.get(key, {})
        to_remove = [
            member for member, score in list(bucket.items())
            if _as_float(score) >= _as_float(min_score) and _as_float(score) <= _as_float(max_score)
        ]
        for member in to_remove:
            bucket.pop(member, None)
        return len(to_remove)

    def zcount(self, key, min_score, max_score):
        bucket = self.store.get(key, {})
        min_val = _as_float(min_score)
        max_val = _as_float(max_score)
        return sum(1 for score in bucket.values() if min_val <= _as_float(score) <= max_val)

    def zrange(self, key, start, end, withscores=False):
        bucket = self.store.get(key, {})
        sorted_items = sorted(bucket.items(), key=lambda item: item[1])
        slice_items = sorted_items[start:end + 1 if end != -1 else None]
        if withscores:
            return [(member, score) for member, score in slice_items]
        return [member for member, _ in slice_items]


def _as_float(value):
    if value in ("+inf", float("inf")):
        return float("inf")
    if value in ("-inf", float("-inf")):
        return float("-inf")
    return float(value)


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


@pytest.mark.unit
def test_rate_limiter_falls_back_when_redis_pipeline_fails():
    limiter = CharacterRateLimiter(redis_client=_FailingRedis(), max_operations=3, window_seconds=60)

    async def run_checks():
        ok1, rem1 = await limiter.check_rate_limit(user_id=42, operation="test")
        ok2, rem2 = await limiter.check_rate_limit(user_id=42, operation="test")
        assert ok1 and ok2
        assert rem1 == 2
        assert rem2 == 1

    asyncio.run(run_checks())


@pytest.mark.unit
def test_rate_limiter_redis_remaining_aligns_with_memory_path():
    limiter = CharacterRateLimiter(redis_client=_InMemoryRedis(), max_operations=3, window_seconds=60)

    async def run_checks():
        ok1, rem1 = await limiter.check_rate_limit(user_id=7, operation="test")
        ok2, rem2 = await limiter.check_rate_limit(user_id=7, operation="test")
        ok3, rem3 = await limiter.check_rate_limit(user_id=7, operation="test")
        assert ok1 and ok2
        assert rem1 == 2 and rem2 == 1
        assert ok3 and rem3 == 0
        with pytest.raises(Exception):
            await limiter.check_rate_limit(user_id=7, operation="test")

    asyncio.run(run_checks())

@pytest.mark.unit
def test_rate_limiter_redis_path_cleans_up_on_rejection():
    redis = _InMemoryRedis()
    limiter = CharacterRateLimiter(redis_client=redis, max_operations=2, window_seconds=60)

    async def run_checks():
        await limiter.check_rate_limit(user_id=55, operation="test")
        await limiter.check_rate_limit(user_id=55, operation="test")
        with pytest.raises(HTTPException):
            await limiter.check_rate_limit(user_id=55, operation="test")

    asyncio.run(run_checks())
    stored = redis.store.get("rate_limit:character:55", {})
    assert len(stored) == 2


@pytest.mark.unit
def test_message_send_rate_redis_path_reports_remaining_consistently():
    limiter = CharacterRateLimiter(redis_client=_InMemoryRedis(), max_message_sends_per_minute=2)

    async def run_checks():
        ok1, rem1 = await limiter.check_message_send_rate(user_id=11)
        ok2, rem2 = await limiter.check_message_send_rate(user_id=11)
        assert ok1 and ok2
        assert rem1 == 1 and rem2 == 0
        with pytest.raises(Exception):
            await limiter.check_message_send_rate(user_id=11)

    asyncio.run(run_checks())


@pytest.mark.unit
def test_message_send_rate_redis_path_cleans_up_on_rejection():
    redis = _InMemoryRedis()
    limiter = CharacterRateLimiter(
        redis_client=redis,
        max_message_sends_per_minute=2
    )

    async def run_checks():
        await limiter.check_message_send_rate(user_id=77)
        await limiter.check_message_send_rate(user_id=77)
        with pytest.raises(HTTPException):
            await limiter.check_message_send_rate(user_id=77)

    asyncio.run(run_checks())
    stored = redis.store.get("rate_limit:message_send:77", {})
    assert len(stored) == 2


@pytest.mark.unit
def test_get_usage_stats_memory_reports_true_reset_time(monkeypatch):
    limiter = CharacterRateLimiter(redis_client=None, max_operations=5, window_seconds=60)
    base_time = 1_000_000.0
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Character_Chat.character_rate_limiter.time.time",
        lambda: base_time,
    )
    limiter.memory_store[123] = [base_time - 30, base_time - 5]

    stats = asyncio.run(limiter.get_usage_stats(123))
    assert stats["operations_used"] == 2
    assert stats["operations_remaining"] == 3
    assert stats["reset_time"] == pytest.approx(base_time + 30)


@pytest.mark.unit
def test_get_usage_stats_redis_reports_true_reset_time(monkeypatch):
    redis = _InMemoryRedis()
    limiter = CharacterRateLimiter(redis_client=redis, max_operations=5, window_seconds=60)
    base_time = 2_000_000.0
    redis.store["rate_limit:character:456"] = {
        "entry1": base_time - 45,
        "entry2": base_time - 10,
    }
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Character_Chat.character_rate_limiter.time.time",
        lambda: base_time,
    )

    stats = asyncio.run(limiter.get_usage_stats(456))
    assert stats["operations_used"] == 2
    assert stats["operations_remaining"] == 3
    assert stats["reset_time"] == pytest.approx(base_time + 15)


@pytest.mark.unit
def test_get_character_rate_limiter_tolerates_invalid_numeric_overrides(monkeypatch):
    import importlib
    module = importlib.import_module("tldw_Server_API.app.core.Character_Chat.character_rate_limiter")

    monkeypatch.setenv("CHARACTER_RATE_LIMIT_OPS", "not-a-number")
    clear_config_cache()
    module._rate_limiter = None
    limiter = module.get_character_rate_limiter()
    assert limiter.max_operations == 100
    module._rate_limiter = None
    monkeypatch.delenv("CHARACTER_RATE_LIMIT_OPS", raising=False)

    clear_config_cache()
    module._rate_limiter = None
    monkeypatch.setitem(settings, "CHARACTER_RATE_LIMIT_OPS", "still-invalid")
    limiter = module.get_character_rate_limiter()
    assert limiter.max_operations == 100
    module._rate_limiter = None
    settings.pop("CHARACTER_RATE_LIMIT_OPS", None)
    clear_config_cache()
