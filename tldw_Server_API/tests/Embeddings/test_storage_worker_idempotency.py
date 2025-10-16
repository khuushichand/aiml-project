import asyncio
from typing import Any, Dict, List

import pytest

from tldw_Server_API.app.core.Embeddings.workers.storage_worker import StorageWorker
from tldw_Server_API.app.core.Embeddings.workers.base_worker import WorkerConfig
from tldw_Server_API.app.core.Embeddings.queue_schemas import StorageMessage, EmbeddingData, JobPriority, UserTier


class FakeCollection:
    def __init__(self):
        self.items: Dict[str, Dict[str, Any]] = {}

    def upsert(self, ids: List[str], embeddings: List[List[float]], documents: List[str], metadatas: List[Dict[str, Any]]):
        for i, _id in enumerate(ids):
            self.items[_id] = {
                "embedding": embeddings[i],
                "document": documents[i],
                "metadata": metadatas[i],
            }

    def add(self, ids: List[str], embeddings: List[List[float]], documents: List[str], metadatas: List[Dict[str, Any]]):
        # mimic add semantics: overwrite for simplicity in test; idempotency relies on upsert path anyway
        self.upsert(ids, embeddings, documents, metadatas)


@pytest.mark.unit
def test_storage_worker_idempotent_upsert(monkeypatch):
    cfg = WorkerConfig(
        worker_id="storage-worker-1",
        worker_type="storage",
        redis_url="redis://localhost:6379",
        queue_name="embeddings:storage",
        consumer_group="storage-group",
        batch_size=10,
        poll_interval_ms=100,
        max_retries=1,
        heartbeat_interval=30,
        shutdown_timeout=30,
        metrics_interval=60,
    )
    worker = StorageWorker(cfg)

    # Patch collection getter to use our fake collection
    fake = FakeCollection()

    async def fake_get_or_create_collection(user_id: str, collection_name: str):
        return fake

    monkeypatch.setattr(worker, "_get_or_create_collection", fake_get_or_create_collection)

    # Provide a dummy redis client to satisfy status updates
    class DummyRedis:
        async def hset(self, *args, **kwargs):
            return 1
        async def expire(self, *args, **kwargs):
            return True

    worker.redis_client = DummyRedis()

    # First message
    msg1 = StorageMessage(
        job_id="job-1",
        user_id="u1",
        media_id=1,
        priority=JobPriority.NORMAL,
        user_tier=UserTier.FREE,
        embeddings=[
            EmbeddingData(chunk_id="c1", embedding=[0.1], model_used="m", dimensions=1, metadata={}),
            EmbeddingData(chunk_id="c2", embedding=[0.2], model_used="m", dimensions=1, metadata={}),
        ],
        collection_name="col",
        total_chunks=2,
        processing_time_ms=10,
        metadata={},
    )

    # Second message repeats one chunk id (c1) with different data
    msg2 = StorageMessage(
        job_id="job-2",
        user_id="u1",
        media_id=1,
        priority=JobPriority.NORMAL,
        user_tier=UserTier.FREE,
        embeddings=[
            EmbeddingData(chunk_id="c1", embedding=[0.9], model_used="m2", dimensions=1, metadata={}),
        ],
        collection_name="col",
        total_chunks=1,
        processing_time_ms=5,
        metadata={},
    )

    asyncio.run(worker.process_message(msg1))
    asyncio.run(worker.process_message(msg2))

    # Idempotency assertions: only two unique ids remain, and c1 got overwritten by msg2
    assert set(fake.items.keys()) == {"c1", "c2"}
    assert fake.items["c1"]["embedding"] == [0.9]
