import asyncio
import pytest

from tldw_Server_API.app.core.Embeddings.workers.storage_worker import StorageWorker
from tldw_Server_API.app.core.Embeddings.workers.base_worker import WorkerConfig
from tldw_Server_API.app.core.Embeddings.queue_schemas import StorageMessage, EmbeddingData
from tldw_Server_API.app.core.RAG.rag_service.vector_stores.base import VectorStoreType


class _FakeAdapter:
    def __init__(self):
        self.deleted_filters = []
        self._initialized = True
        class _Cfg:
            def __init__(self, t): self.store_type = t; self.connection_params = {}
        self.config = _Cfg(VectorStoreType.PGVECTOR)
    async def initialize(self):
        self._initialized = True
    async def create_collection(self, collection_name, metadata=None):
        return None
    async def delete_by_filter(self, collection_name, f):
        self.deleted_filters.append((collection_name, f))
        return 1
    async def upsert_vectors(self, *a, **k):
        return None


def _build_message() -> StorageMessage:
    emb = EmbeddingData(
        chunk_id="c1",
        embedding=[0.1, 0.2, 0.3],
        model_used="test-model",
        dimensions=3,
        metadata={"kind": "chunk"},
    )
    return StorageMessage(
        job_id="j1",
        user_id="1",
        media_id=7,
        embeddings=[emb],
        collection_name="user_1_media_embeddings",
        total_chunks=1,
        processing_time_ms=1,
        metadata={},
    )


@pytest.mark.parametrize("store_type", [VectorStoreType.PGVECTOR, VectorStoreType.CHROMADB])
def test_soft_delete_uses_delete_by_filter(monkeypatch, store_type):
    from tldw_Server_API.app.core.RAG.rag_service import vector_stores as _vs

    base = type("_Base", (), {"config": type("_Cfg", (), {"store_type": store_type, "connection_params": {}})})()
    monkeypatch.setattr(_vs.VectorStoreFactory, "create_from_settings", classmethod(lambda cls, settings, user_id='0': base))

    fake = _FakeAdapter()
    fake.config.store_type = store_type

    async def _fake_get_adapter_for_user(self, user_id: str, dim: int):
        return fake

    async def _is_soft_deleted(self, media_id: int) -> bool:
        return True

    cfg = WorkerConfig(worker_id="w1", worker_type="storage", queue_name="embeddings:storage", consumer_group="g1")
    worker = StorageWorker(cfg)
    worker.redis_client = type("_R", (), {"set": lambda *a, **k: None, "hset": lambda *a, **k: None})()

    monkeypatch.setattr(StorageWorker, "_get_adapter_for_user", _fake_get_adapter_for_user)
    monkeypatch.setattr(StorageWorker, "_is_media_soft_deleted", _is_soft_deleted)

    msg = _build_message()
    asyncio.run(worker.process_message(msg))
    # Ensure delete_by_filter was invoked
    assert fake.deleted_filters and fake.deleted_filters[0][0] == msg.collection_name
    assert fake.deleted_filters[0][1] == {"media_id": str(msg.media_id)}
