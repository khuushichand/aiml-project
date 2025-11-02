import asyncio
import json
import pytest

from tldw_Server_API.app.core.Embeddings.workers.base_worker import BaseWorker, WorkerConfig
from tldw_Server_API.app.core.Embeddings.queue_schemas import EmbeddingJobMessage


class _FakeRedis:
    def __init__(self):
        self.zsets = {}
        self.streams = {}
        self.hashes = {}

    # Delayed queue operations
    async def zadd(self, key, mapping):
        arr = self.zsets.setdefault(key, [])
        for member, score in mapping.items():
            arr.append((float(score), str(member)))
        # keep sorted by score
        arr.sort(key=lambda x: x[0])
        return True

    # Live stream ops
    async def xadd(self, name, fields):
        arr = self.streams.setdefault(name, [])
        eid = f"{len(arr)+1}-0"
        arr.append((eid, dict(fields)))
        return eid

    async def xack(self, stream, group, message_id):
        return 1

    # Status/hash
    async def hset(self, key, mapping=None, **kwargs):
        m = dict(mapping or {})
        self.hashes.setdefault(key, {}).update(m)
        return True

    async def expire(self, key, ttl):
        return True

    async def get(self, key):
        return None


class _TestWorker(BaseWorker):
    def __init__(self):
        cfg = WorkerConfig(
            worker_id="embedding-0",
            worker_type="embedding",
            redis_url="redis://localhost:6379",
            queue_name="embeddings:embedding",
            consumer_group="embedding-workers",
        )
        super().__init__(cfg)
        # Inject fake redis
        self.redis_client = _FakeRedis()

    async def process_message(self, message):
        return None

    def _parse_message(self, data):
        if isinstance(data, EmbeddingJobMessage):
            return data
        return EmbeddingJobMessage(
            job_id=data.get("job_id", "job-1"),
            user_id=data.get("user_id", "u"),
            media_id=int(data.get("media_id", 1)),
            retry_count=int(data.get("retry_count", 0)),
            max_retries=int(data.get("max_retries", 2)),
        )

    async def _send_to_next_stage(self, result):
        return None


@pytest.mark.unit
def test_permanent_failure_goes_to_dlq():
    w = _TestWorker()
    msg = {
        "job_id": "job-perm",
        "user_id": "u",
        "media_id": 1,
        "retry_count": 0,
        "max_retries": 3,
    }
    # Simulate ValueError (permanent)
    asyncio.run(w._handle_failed_message("1-0", msg, ValueError("bad input")))
    dlq = w.redis_client.streams.get("embeddings:embedding:dlq", [])
    assert len(dlq) == 1
    _, fields = dlq[0]
    assert fields.get("job_id") == "job-perm"
    assert fields.get("error_code") == "INVALID_INPUT"
    assert fields.get("failure_type") == "permanent"


@pytest.mark.unit
def test_transient_failure_schedules_retry():
    w = _TestWorker()
    msg = {
        "job_id": "job-trans",
        "user_id": "u",
        "media_id": 1,
        "retry_count": 0,
        "max_retries": 3,
    }
    # Simulate TimeoutError (transient)
    asyncio.run(w._handle_failed_message("1-0", msg, TimeoutError("timeout")))
    delayed_key = f"{w.config.queue_name}:delayed"
    assert delayed_key in w.redis_client.zsets
    assert len(w.redis_client.zsets[delayed_key]) == 1
