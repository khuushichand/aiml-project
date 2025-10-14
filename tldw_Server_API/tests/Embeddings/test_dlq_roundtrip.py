import asyncio
import json
from datetime import datetime

import pytest

from tldw_Server_API.app.core.Embeddings.workers.base_worker import BaseWorker, WorkerConfig
from tldw_Server_API.app.core.Embeddings.queue_schemas import EmbeddingMessage, ChunkData, JobPriority, UserTier


class InMemoryRedis:
    def __init__(self):
        self.streams = {}
        self.hashes = {}

    async def xadd(self, name, fields):
        arr = self.streams.setdefault(name, [])
        arr.append((str(len(arr)+1)+"-0", fields))
        return arr[-1][0]

    async def xack(self, name, group, *ids):
        return len(ids)

    async def hset(self, name, mapping=None, **kwargs):
        mp = mapping.copy() if mapping else {}
        mp.update(kwargs)
        d = self.hashes.setdefault(name, {})
        d.update(mp)
        return len(mp)


class DummyEmbeddingWorker(BaseWorker):
    def _parse_message(self, data):
        return EmbeddingMessage(**data) if isinstance(data, dict) else data

    async def process_message(self, message):
        raise RuntimeError("forced failure")

    async def _send_to_next_stage(self, result):
        pass


@pytest.mark.unit
def test_dlq_on_max_retries(monkeypatch):
    cfg = WorkerConfig(
        worker_id="w1",
        worker_type="embedding",
        redis_url="redis://localhost:6379",
        queue_name="embeddings:embedding",
        consumer_group="embedding-group",
        batch_size=1,
        poll_interval_ms=10,
        max_retries=1,
        heartbeat_interval=30,
        shutdown_timeout=30,
        metrics_interval=60,
    )
    worker = DummyEmbeddingWorker(cfg)
    r = InMemoryRedis()
    worker.redis_client = r

    # Compose a message and push into failure path twice: second time should hit DLQ
    msg = EmbeddingMessage(
        job_id="job-1",
        user_id="u1",
        media_id=1,
        priority=JobPriority.NORMAL,
        user_tier=UserTier.FREE,
        max_retries=1,
        chunks=[ChunkData(chunk_id="c1", content="t", metadata={}, start_index=0, end_index=1, sequence_number=0)],
        embedding_model_config={"model_name": "m"},
        model_provider="huggingface",
    )

    # First failure: requeue with retry_count=1
    asyncio.run(worker._handle_failed_message("1-0", msg.model_dump(), RuntimeError("e1")))
    # Second failure: exceeds max_retries -> DLQ
    msg_retry = msg.model_copy(update={"retry_count": 1, "max_retries": 1})
    asyncio.run(worker._handle_failed_message("2-0", msg_retry.model_dump(), RuntimeError("e2")))

    dlq_name = "embeddings:embedding:dlq"
    assert dlq_name in r.streams
    # One DLQ entry should exist
    assert len(r.streams[dlq_name]) == 1
    _, fields = r.streams[dlq_name][0]
    assert fields.get("job_id") == "job-1"
    assert "error" in fields
