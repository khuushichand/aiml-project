import asyncio
import pytest

from tldw_Server_API.app.core.Embeddings.workers.storage_worker import StorageWorker
from tldw_Server_API.app.core.Embeddings.workers.base_worker import WorkerConfig
from tldw_Server_API.app.core.Embeddings.queue_schemas import StorageMessage, EmbeddingData


class _FakeRedis:
    def __init__(self):
        self.kv = {}
        self.streams = {}
        self.hashes = {}

    async def get(self, key):
        return self.kv.get(key)

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.kv:
            return False
        self.kv[key] = value
        return True

    async def xadd(self, name, fields):
        self.streams.setdefault(name, []).append(fields)
        return "1-0"

    async def hset(self, key, mapping=None, **kwargs):
        m = dict(mapping or {})
        self.hashes.setdefault(key, {}).update(m)
        return True

    async def expire(self, key, ttl):
        return True


class _TestStorageWorker(StorageWorker):
    async def _get_or_create_collection(self, user_id: str, collection_name: str):
        class _Dummy:
            metadata = {"embedder_name": "huggingface", "embedder_version": "model-v1"}

            def add(self, **kwargs):
                return True
        return _Dummy()

    async def _update_database(self, media_id: int, total_chunks: int):
        return None


@pytest.mark.unit
def test_storage_idempotency_short_circuit(monkeypatch):
    cfg = WorkerConfig(
        worker_id="storage-0",
        worker_type="storage",
        redis_url="redis://localhost:6379",
        queue_name="embeddings:storage",
        consumer_group="storage-workers",
    )
    w = _TestStorageWorker(cfg)
    fake = _FakeRedis()
    w.redis_client = fake
    # Ledger indicates completed for idempotency key
    asyncio.run(fake.set("embeddings:ledger:idemp:idem-1", "completed"))

    msg = StorageMessage(
        job_id="job-x",
        user_id="u",
        media_id=1,
        idempotency_key="idem-1",
        dedupe_key=None,
        embeddings=[EmbeddingData(chunk_id="c1", embedding=[0.1,0.2], model_used="m", dimensions=2, metadata={})],
        collection_name="col",
        total_chunks=1,
        processing_time_ms=1,
    )

    # Should short-circuit to completed without error
    asyncio.run(w.process_message(msg))
    st = asyncio.run(fake.get("embeddings:ledger:idemp:idem-1"))
    assert st == "completed"
