import asyncio
import types
import pytest


class FakeRedis:
    def __init__(self):
        self.streams = []
        self.hashes = {}
        self.sets = {}
        self.zsets = {}

    async def xadd(self, name, fields):
        self.streams.append((name, fields))
        return "1-0"

    async def hset(self, key, mapping=None, **kwargs):
        self.hashes[key] = dict(mapping or {})

    async def expire(self, key, seconds):
        return True

    async def sadd(self, key, member):
        self.sets.setdefault(key, set()).add(member)

    async def zadd(self, key, mapping):
        self.zsets.setdefault(key, {}).update(mapping)

    async def zremrangebyscore(self, key, min, max):
        return 0


class FakeQuota:
    async def check_quota(self, user_id, user_tier, chunks_requested):
        return True

    async def consume_quota(self, user_id, chunks_used):
        return None


class FakePriority:
    async def calculate_priority(self, user_id, user_tier, base_priority, created_at):
        return base_priority


@pytest.mark.asyncio
async def test_jobmanager_enqueues_with_trace_id(monkeypatch):
    # Arrange
    from tldw_Server_API.app.core.Embeddings import job_manager as jm

    fake_tm = types.SimpleNamespace()
    class _SpanCtx:
        is_valid = True
        trace_id = int("1234", 16)  # small hex
    class _Span:
        def get_span_context(self):
            return _SpanCtx()
    fake_tm.get_current_span = lambda: _Span()
    monkeypatch.setattr(jm, "get_tracing_manager", lambda: fake_tm)

    mgr = jm.EmbeddingJobManager(jm.JobManagerConfig())
    mgr.redis_client = FakeRedis()
    mgr.quota_manager = FakeQuota()
    mgr.priority_calculator = FakePriority()

    # Act
    job_id = await mgr.create_job(
        media_id=1,
        user_id="u1",
        user_tier=jm.UserTier.FREE,
        content="hello world",
        content_type="text",
        priority=jm.JobPriority.NORMAL,
        metadata={}
    )

    # Assert
    assert job_id
    # First xadd should be to chunking queue
    name, fields = mgr.redis_client.streams[-1]
    assert name == mgr.config.chunking_queue
    # Message carries trace_id
    assert "trace_id" in fields
    assert isinstance(fields["trace_id"], str)
    assert len(fields["trace_id"]) > 0
