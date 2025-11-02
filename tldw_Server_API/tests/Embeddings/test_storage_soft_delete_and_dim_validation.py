import asyncio
import pytest

from tldw_Server_API.app.core.Embeddings.workers.storage_worker import StorageWorker
from tldw_Server_API.app.core.Embeddings.workers.base_worker import WorkerConfig
from tldw_Server_API.app.core.Embeddings.queue_schemas import StorageMessage, EmbeddingData


class _FakeRedis:
    def __init__(self):
        self.kv = {}
        self.hashes = {}

    async def set(self, key, value, ex=None):
        self.kv[key] = value
        return True

    async def hset(self, key, mapping=None, **kwargs):
        m = dict(mapping or {})
        self.hashes.setdefault(key, {}).update(m)
        return True


class _FakeCollection:
    def __init__(self, metadata=None):
        self.metadata = dict(metadata or {})
        self.deleted_where = None
        self._embs = {}

    def delete(self, where=None, ids=None):
        self.deleted_where = where or {}

    def get(self, limit=1, include=None):
        # Return one existing embedding to simulate existing dimension when metadata absent
        if include and 'embeddings' in include:
            return {'embeddings': [[0.0, 0.0, 0.0, 0.0]]}
        return {}

    def upsert(self, **kwargs):
        return None

    def add(self, **kwargs):
        return None


class _StorageSoftDelete(StorageWorker):
    def __init__(self, cfg, fake_collection):
        super().__init__(cfg)
        self._fake_collection = fake_collection

    async def _get_or_create_collection(self, user_id: str, collection_name: str, collection_metadata=None):
        # Inject metadata onto fake collection too
        if collection_metadata:
            try:
                self._fake_collection.metadata.update(collection_metadata)
            except Exception:
                pass
        return self._fake_collection

    async def _is_media_soft_deleted(self, media_id: int) -> bool:
        return True


@pytest.mark.unit
def test_storage_soft_delete_propagates_delete(monkeypatch):
    cfg = WorkerConfig(
        worker_id="storage-1",
        worker_type="storage",
        redis_url="redis://localhost:6379",
        queue_name="embeddings:storage",
        consumer_group="storage-workers",
    )
    fake_coll = _FakeCollection(metadata={})
    w = _StorageSoftDelete(cfg, fake_coll)
    w.redis_client = _FakeRedis()

    msg = StorageMessage(
        job_id="job-del",
        user_id="u",
        media_id=42,
        embeddings=[EmbeddingData(chunk_id="c1", embedding=[0.1,0.2], model_used="m", dimensions=2, metadata={})],
        collection_name="user_u_media_42",
        total_chunks=1,
        processing_time_ms=1,
    )
    asyncio.run(w.process_message(msg))
    assert fake_coll.deleted_where == {"media_id": str(42)}


class _StorageDimCheck(StorageWorker):
    def __init__(self, cfg, fake_collection):
        super().__init__(cfg)
        self._fake_collection = fake_collection

    async def _get_or_create_collection(self, user_id: str, collection_name: str, collection_metadata=None):
        return self._fake_collection


@pytest.mark.unit
def test_storage_dim_mismatch_hard_error(monkeypatch):
    cfg = WorkerConfig(
        worker_id="storage-2",
        worker_type="storage",
        redis_url="redis://localhost:6379",
        queue_name="embeddings:storage",
        consumer_group="storage-workers",
    )
    # Fake collection expects dim 4
    fake_coll = _FakeCollection(metadata={"embedding_dimension": 4})
    w = _StorageDimCheck(cfg, fake_coll)
    w.redis_client = _FakeRedis()

    msg = StorageMessage(
        job_id="job-dim",
        user_id="u",
        media_id=9,
        embeddings=[EmbeddingData(chunk_id="c2", embedding=[0.1,0.2], model_used="m", dimensions=2, metadata={})],
        collection_name="user_u_media_9",
        total_chunks=1,
        processing_time_ms=1,
    )
    with pytest.raises(RuntimeError):
        asyncio.run(w.process_message(msg))
