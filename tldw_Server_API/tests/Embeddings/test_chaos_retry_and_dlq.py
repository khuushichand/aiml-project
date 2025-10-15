import json
import time

import pytest

from tldw_Server_API.app.core.Embeddings.workers.base_worker import BaseWorker, WorkerConfig
from tldw_Server_API.app.core.Embeddings.queue_schemas import EmbeddingMessage


class FakeAsyncRedisChaos:
    def __init__(self):
        self.zsets = {}
        self.streams = {}
        self.acks = []
        self.kv = {}

    async def zadd(self, key, mapping):
        arr = self.zsets.setdefault(key, [])
        for payload, score in mapping.items():
            arr.append((payload, score))
        return len(mapping)

    async def xadd(self, name, fields):
        lst = self.streams.setdefault(name, [])
        eid = f"{len(lst)+1}-0"
        # coerce values to strings for consistency
        f = {k: (v if isinstance(v, str) else json.dumps(v)) for k, v in fields.items()}
        lst.append((eid, f))
        return eid

    async def xack(self, name, group, *ids):
        self.acks.append((name, group, ids))
        return len(ids)

    async def hset(self, key, mapping=None, **kwargs):  # noqa: ARG002
        # ignore
        return 1

    async def set(self, key, value, ex=None, nx=False):  # noqa: ARG002
        self.kv[key] = value
        return True

    async def get(self, key):
        return self.kv.get(key)


class ChaosWorker(BaseWorker):
    def _parse_message(self, data):
        return EmbeddingMessage(**data)

    async def process_message(self, message):  # pragma: no cover - not used directly here
        raise NotImplementedError

    async def _send_to_next_stage(self, result):  # pragma: no cover - not used
        return None


def _mk_config():
    return WorkerConfig(
        worker_id="w1",
        worker_type="embedding",
        queue_name="embeddings:embedding",
        consumer_group="cg",
        max_retries=2,
    )


def _mk_msg(retry_count=0):
    return {
        "job_id": "job-1",
        "user_id": "u",
        "media_id": 1,
        "priority": 1,
        "user_tier": "pro",
        "created_at": "2025-01-01T00:00:00Z",
        "retry_count": retry_count,
        "max_retries": 2,
        "chunks": [],
    }


class HTTP429(Exception):
    status = 429


class HTTP500(Exception):
    status_code = 500


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transient_errors_schedule_retry(monkeypatch):
    w = ChaosWorker(_mk_config())
    fake = FakeAsyncRedisChaos()
    w.redis_client = fake

    data = _mk_msg(retry_count=0)
    # Drive the internal failure handler directly
    # Simulate a transient 429 which should schedule retry in delayed ZSET
    await w._handle_failed_message("1-0", data, HTTP429("rl"))
    # zset key should get one entry
    delayed_key = f"{w.config.queue_name}:delayed"
    assert delayed_key in fake.zsets
    assert len(fake.zsets[delayed_key]) == 1
    # No DLQ entry on first transient failure
    assert f"{w.config.queue_name}:dlq" not in fake.streams


@pytest.mark.unit
@pytest.mark.asyncio
async def test_exhausted_retries_go_to_dlq(monkeypatch):
    w = ChaosWorker(_mk_config())
    fake = FakeAsyncRedisChaos()
    w.redis_client = fake
    # Already at max retry -> DLQ
    data = _mk_msg(retry_count=2)
    await w._handle_failed_message("1-0", data, HTTP500("boom"))
    dlq = fake.streams.get("embeddings:embedding:dlq", [])
    assert len(dlq) == 1
    fields = dlq[0][1]
    assert json.loads(fields.get("payload", "{}")).get("job_id") == "job-1"
    assert fields.get("error_code")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_permanent_error_direct_dlq():
    w = ChaosWorker(_mk_config())
    fake = FakeAsyncRedisChaos()
    w.redis_client = fake
    data = _mk_msg(retry_count=0)
    # ValueError is classified as permanent (INVALID_INPUT)
    await w._handle_failed_message("1-0", data, ValueError("bad"))
    dlq = fake.streams.get("embeddings:embedding:dlq", [])
    assert len(dlq) == 1
