from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.AuthNZ import rate_limiter as rate_limiter_module
from tldw_Server_API.app.core.AuthNZ.rate_limiter import RateLimiter


class _FixedDatetime(rate_limiter_module.datetime):
    """Subclass datetime to override utcnow while preserving other behaviour."""

    @classmethod
    def utcnow(cls):
        return cls(2024, 1, 1, 12, 5, 42)


class _FakePipeline:
    def __init__(self, client):
        self.client = client
        self.ops = []

    def incr(self, key):
        self.ops.append(("incr", key))

    def expire(self, key, ttl):
        self.ops.append(("expire", key, ttl))

    async def execute(self):
        results = []
        for op in self.ops:
            if op[0] == "incr":
                key = op[1]
                value = self.client.counts.get(key, 0) + 1
                self.client.counts[key] = value
                results.append(value)
            else:
                key, ttl = op[1], op[2]
                self.client.ttls[key] = ttl
                results.append(True)
        self.client.operation_history.append(list(self.ops))
        self.ops.clear()
        return results


class _FakeRedis:
    def __init__(self):
        self.counts = {}
        self.ttls = {}
        self.operation_history = []

    def pipeline(self):
        return _FakePipeline(self)

    async def get(self, key):
        if key in self.counts:
            return str(self.counts[key])
        return None

    async def ttl(self, key):
        return self.ttls.get(key, -2)


@pytest.mark.asyncio
async def test_redis_window_alignment(monkeypatch):
    original_datetime = rate_limiter_module.datetime
    try:
        monkeypatch.setattr(rate_limiter_module, "datetime", _FixedDatetime)

        settings = SimpleNamespace(
            RATE_LIMIT_ENABLED=True,
            RATE_LIMIT_PER_MINUTE=1,
            RATE_LIMIT_BURST=0,
            SERVICE_ACCOUNT_RATE_LIMIT=60,
            REDIS_URL="redis://fake",
        )
        limiter = RateLimiter(settings=settings)
        limiter._initialized = True
        limiter.redis_client = _FakeRedis()

        identifier = "user-1"
        endpoint = "/api/test"
        hashed_key = limiter._create_key(identifier, endpoint)
        expected_window = "20240101120500"

        allowed, meta = await limiter.check_rate_limit(
            identifier, endpoint, limit=1, burst=0, window_minutes=1
        )
        assert allowed is True
        assert meta["reset_time"].startswith("2024-01-01T12:06")

        recorded_ops = limiter.redis_client.operation_history[-1]
        increment_key = next(op[1] for op in recorded_ops if op[0] == "incr")
        assert increment_key == f"rate:{hashed_key}:{expected_window}"

        allowed_second, meta_second = await limiter.check_rate_limit(
            identifier, endpoint, limit=1, burst=0, window_minutes=1
        )
        assert allowed_second is False
        assert meta_second["remaining"] == 0
        assert meta_second["reset_time"].startswith("2024-01-01T12:06")
        assert meta_second["retry_after"] == 18  # 60s window - 42s elapsed
    finally:
        monkeypatch.setattr(rate_limiter_module, "datetime", original_datetime)


class _FiveMinuteDatetime(rate_limiter_module.datetime):
    @classmethod
    def utcnow(cls):
        return cls(2024, 1, 1, 12, 7, 42)


@pytest.mark.asyncio
async def test_redis_window_alignment_multi_minute(monkeypatch):
    original_datetime = rate_limiter_module.datetime
    try:
        monkeypatch.setattr(rate_limiter_module, "datetime", _FiveMinuteDatetime)

        settings = SimpleNamespace(
            RATE_LIMIT_ENABLED=True,
            RATE_LIMIT_PER_MINUTE=10,
            RATE_LIMIT_BURST=0,
            SERVICE_ACCOUNT_RATE_LIMIT=60,
            REDIS_URL="redis://fake",
        )
        limiter = RateLimiter(settings=settings)
        limiter._initialized = True
        limiter.redis_client = _FakeRedis()

        identifier = "user-5"
        endpoint = "/api/test"
        hashed_key = limiter._create_key(identifier, endpoint)

        allowed, meta = await limiter.check_rate_limit(
            identifier, endpoint, limit=10, burst=0, window_minutes=5
        )
        assert allowed is True
        assert meta["reset_time"].startswith("2024-01-01T12:10")

        recorded_ops = limiter.redis_client.operation_history[-1]
        increment_key = next(op[1] for op in recorded_ops if op[0] == "incr")
        assert increment_key == f"rate:{hashed_key}:20240101120500"
    finally:
        monkeypatch.setattr(rate_limiter_module, "datetime", original_datetime)
