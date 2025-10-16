import asyncio
import os
from typing import Any, Dict, List, Optional

import pytest

from tldw_Server_API.app.core.Embeddings.workers.storage_worker import StorageWorker
from tldw_Server_API.app.core.Embeddings.workers.base_worker import WorkerConfig
from tldw_Server_API.app.core.Embeddings.queue_schemas import StorageMessage, EmbeddingData
from tldw_Server_API.app.core.RAG.rag_service.vector_stores.base import VectorStoreType


class _FakeAdapter:
    def __init__(self):
        class _Cfg:
            store_type = VectorStoreType.PGVECTOR
            connection_params = {}
        self.config = _Cfg()
        self.created: Optional[Dict[str, Any]] = None
        self.upsert_calls: List[Dict[str, Any]] = []
        self._initialized = True

    async def initialize(self):
        self._initialized = True

    async def create_collection(self, collection_name: str, metadata: Optional[Dict[str, Any]] = None):
        self.created = {"name": collection_name, "metadata": metadata or {}}

    async def upsert_vectors(self, collection_name: str, ids: List[str], vectors: List[List[float]], documents: List[str], metadatas: List[Dict[str, Any]]):
        self.upsert_calls.append({
            "collection": collection_name,
            "ids": ids,
            "vectors": vectors,
            "documents": documents,
            "metadatas": metadatas,
        })


class _FakeRedis:
    def __init__(self):
        self.kv: Dict[str, Any] = {}

    async def get(self, key: str):
        return self.kv.get(key)

    async def set(self, key: str, value: Any, ex: Optional[int] = None):
        self.kv[key] = value

    async def hset(self, key: str, mapping: Dict[str, Any]):
        self.kv.setdefault(key, {}).update(mapping)

    async def xadd(self, stream: str, fields: Dict[str, Any]):
        return "0-0"


def test_storage_worker_uses_pgvector_adapter(monkeypatch):
    # Force settings path that selects pgvector via factory probe
    fake_base = type("_Base", (), {"config": type("_Cfg", (), {"store_type": VectorStoreType.PGVECTOR, "connection_params": {}})})()

    from tldw_Server_API.app.core.RAG.rag_service import vector_stores as _vs

    monkeypatch.setattr(
        _vs.VectorStoreFactory,
        "create_from_settings",
        classmethod(lambda cls, _settings, user_id="0": fake_base),
    )

    # Fake adapter returned by worker helper
    fake_adapter = _FakeAdapter()

    async def _fake_get_adapter_for_user(self, user_id: str, dim: int):
        return fake_adapter

    # Track if chroma path is used
    called_store_batch = {"value": False}

    async def _fake_store_batch(self, collection, ids, embeddings, documents, metadatas):
        called_store_batch["value"] = True

    async def _fake_is_soft_deleted(self, media_id: int) -> bool:
        return False

    # Build worker
    cfg = WorkerConfig(worker_id="w1", worker_type="storage", queue_name="embeddings:storage", consumer_group="g1")
    worker = StorageWorker(cfg)
    worker.redis_client = _FakeRedis()

    monkeypatch.setattr(StorageWorker, "_get_adapter_for_user", _fake_get_adapter_for_user)
    monkeypatch.setattr(StorageWorker, "_store_batch", _fake_store_batch)
    monkeypatch.setattr(StorageWorker, "_is_media_soft_deleted", _fake_is_soft_deleted)

    # Build message with one embedding
    emb = EmbeddingData(
        chunk_id="c1",
        embedding=[0.1, 0.2, 0.3],
        model_used="test-model",
        dimensions=3,
        metadata={"kind": "chunk"},
    )
    msg = StorageMessage(
        job_id="j1",
        user_id="1",
        media_id=42,
        idempotency_key="idem-1",
        dedupe_key="dedupe-1",
        embeddings=[emb],
        collection_name="user_1_media_embeddings",
        total_chunks=1,
        processing_time_ms=5,
        metadata={},
    )

    asyncio.run(worker.process_message(msg))

    # Assert adapter path used
    assert fake_adapter.created is not None
    assert len(fake_adapter.upsert_calls) == 1
    # And chroma _store_batch was not used
    assert called_store_batch["value"] is False
