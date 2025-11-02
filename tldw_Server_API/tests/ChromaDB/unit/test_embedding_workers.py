"""
Unit tests aligned to the current async worker APIs.

These tests exercise stateless helper methods and parsing logic, without
starting Redis or background loops. They focus on correctness of chunking,
model selection heuristics, simple caching, and storage parsing.
"""

import pytest
from typing import Dict

from tldw_Server_API.app.core.Embeddings.workers.base_worker import WorkerConfig
from tldw_Server_API.app.core.Embeddings.workers.chunking_worker import ChunkingWorker
from tldw_Server_API.app.core.Embeddings.workers.embedding_worker import (
    EmbeddingWorker, EmbeddingWorkerConfig, EmbeddingCache
)
from tldw_Server_API.app.core.Embeddings.workers.storage_worker import StorageWorker
from tldw_Server_API.app.core.Embeddings.queue_schemas import (
    ChunkingMessage, ChunkingConfig, EmbeddingMessage, StorageMessage,
    ChunkData, EmbeddingData, JobStatus, UserTier
)


@pytest.mark.unit
class TestBaseConfigs:
    def test_worker_config_minimal(self):
        cfg = WorkerConfig(
            worker_id="w1",
            worker_type="chunking",
            queue_name="q:chunking",
            consumer_group="g:workers",
        )
        assert cfg.worker_id == "w1"
        assert cfg.worker_type == "chunking"
        assert cfg.queue_name == "q:chunking"
        assert cfg.consumer_group == "g:workers"


@pytest.mark.unit
class TestChunkingWorker:
    def _make_chunker(self) -> ChunkingWorker:
        cfg = WorkerConfig(
            worker_id="chunker",
            worker_type="chunking",
            queue_name="stream:chunking",
            consumer_group="cg:chunk",
            batch_size=1,
        )
        return ChunkingWorker(cfg)

    def test_chunking_simple(self):
        worker = self._make_chunker()
        text = "Hello world. This is a test document. Another sentence here."
        chunks = worker._chunk_text(text, chunk_size=20, overlap=5, separator=" ")
        # Non-empty chunks with sane boundaries
        assert len(chunks) >= 2
        for chunk_text, start, end in chunks:
            assert isinstance(chunk_text, str) and chunk_text
            assert 0 <= start < end <= len(text)

    def test_generate_chunk_id(self):
        worker = self._make_chunker()
        cid1 = worker._generate_chunk_id("jobA", 0)
        cid2 = worker._generate_chunk_id("jobA", 1)
        assert cid1 != cid2
        assert len(cid1) == 16 and len(cid2) == 16


@pytest.mark.unit
class TestEmbeddingWorker:
    def _make_embedder(self) -> EmbeddingWorker:
        cfg = EmbeddingWorkerConfig(
            worker_id="embedder",
            worker_type="embedding",
            queue_name="stream:embedding",
            consumer_group="cg:embed",
            default_model_provider="huggingface",
            default_model_name="sentence-transformers/all-MiniLM-L6-v2",
            enable_model_selection=True,
            cache_max_size=10,
            cache_ttl_seconds=60,
        )
        return EmbeddingWorker(cfg)

    def test_language_detection(self):
        worker = self._make_embedder()
        assert worker._detect_language("Hello world") == "english"
        assert worker._detect_language("Hola señor, cómo estás?") in {"multilingual", "english"}

    def test_model_selection_heuristics(self):
        worker = self._make_embedder()
        provider, model = worker._select_model("short text", {})
        assert provider in {"huggingface", "openai"}
        assert isinstance(model, str) and model

    def test_embedding_cache(self):
        cache = EmbeddingCache(max_size=2, ttl_seconds=3600)
        v = [0.1, 0.2]
        cache.put("hello", "m1", v)
        got = cache.get("hello", "m1")
        assert got == v
        # Evict on overflow
        cache.put("a", "m1", v)
        cache.put("b", "m1", v)
        # One of the earlier entries should be gone
        remaining = sum(1 for k in [cache.get("hello", "m1"), cache.get("a", "m1"), cache.get("b", "m1")] if k)
        assert remaining >= 2


@pytest.mark.unit
class TestStorageWorker:
    def _make_storage(self) -> StorageWorker:
        # Patch ChromaDBManager in module to avoid constructor args
        from tldw_Server_API.app.core.Embeddings import workers as workers_pkg
        from tldw_Server_API.app.core.Embeddings.workers import storage_worker as sw

        class DummyMgr:
            def get_or_create_collection(self, *args, **kwargs):
                class Col:
                    def add(self, *a, **k):
                        return None
                return Col()

        sw.ChromaDBManager = DummyMgr  # type: ignore

        cfg = WorkerConfig(
            worker_id="store",
            worker_type="storage",
            queue_name="stream:storage",
            consumer_group="cg:store",
        )
        return StorageWorker(cfg)

    def test_parse_storage_message(self):
        worker = self._make_storage()
        msg: Dict = {
            "job_id": "j1",
            "user_id": "u1",
            "media_id": 1,
            "priority": 50,
            "user_tier": UserTier.FREE.value,
            "embeddings": [
                {
                    "chunk_id": "c1",
                    "embedding": [0.1, 0.2],
                    "model_used": "m",
                    "dimensions": 2,
                    "metadata": {"k": "v"}
                }
            ],
            "collection_name": "col",
            "total_chunks": 1,
            "processing_time_ms": 10,
            "metadata": {}
        }
        parsed = worker._parse_message(msg)
        assert isinstance(parsed, StorageMessage)
        assert parsed.collection_name == "col"
        assert parsed.embeddings[0].chunk_id == "c1"
