import asyncio
import json
import pytest

from tldw_Server_API.app.core.Embeddings.workers.embedding_worker import EmbeddingWorker, EmbeddingWorkerConfig
from tldw_Server_API.app.core.Embeddings.queue_schemas import EmbeddingMessage, ChunkData


class _FakeRedis:
    def __init__(self):
        self.kv = {}
        self.hashes = {}

    async def get(self, key):
        return self.kv.get(key)

    async def set(self, key, value, ex=None):
        self.kv[key] = value
        return True

    async def hset(self, key, mapping=None, **kwargs):
        m = dict(mapping or {})
        self.hashes.setdefault(key, {}).update(m)
        return True

    async def expire(self, key, ttl):
        return True


class _TestEmbeddingWorker(EmbeddingWorker):
    async def _generate_embeddings(self, texts, model_config, model_provider):
        # Fail if called; we expect cache hit
        raise RuntimeError("Should not be called when Redis cache is hit")


@pytest.mark.unit
def test_embedding_uses_redis_content_hash_cache(monkeypatch):
    cfg = EmbeddingWorkerConfig(
        worker_id="embedding-0",
        worker_type="embedding",
        redis_url="redis://localhost:6379",
        queue_name="embeddings:embedding",
        consumer_group="embedding-workers",
        enable_caching=False,
    )
    w = _TestEmbeddingWorker(cfg)
    fake = _FakeRedis()
    w.redis_client = fake

    chash = "abcd1234"
    model_name = w.embedding_config.default_model_name
    key = f"embeddings:contentcache:v1:{model_name}:{chash}"
    asyncio.run(fake.set(key, json.dumps({"embedding": [0.5, 0.6], "dimensions": 2, "model": model_name, "provider": "huggingface", "ts": 0})))

    msg = EmbeddingMessage(
        job_id="job-1",
        user_id="u",
        media_id=1,
        chunks=[ChunkData(chunk_id="c1", content="text", metadata={"content_hash": chash}, start_index=0, end_index=4, sequence_number=0)],
        embedding_model_config={},
        model_provider="huggingface",
    )

    out = asyncio.run(w.process_message(msg))
    assert out is not None
    assert out.embeddings[0].embedding == [0.5, 0.6]
    assert out.embeddings[0].metadata.get("cached") is True
