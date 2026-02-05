import numpy as np
import pytest

from tldw_Server_API.app.core.RAG.rag_service.semantic_cache import SemanticCache


pytestmark = pytest.mark.unit


class DummyEmbedder:
    async def embed(self, _text: str):
        return np.array([1.0, 0.0], dtype=float)


@pytest.mark.asyncio
async def test_semantic_cache_save_load_and_find_similar(tmp_path):
    cache_path = tmp_path / "semantic_cache.json"
    cache = SemanticCache(
        similarity_threshold=0.8,
        ttl=10,
        persist_path=str(cache_path),
        embedding_model=DummyEmbedder(),
        namespace="tenant-1",
    )

    await cache.set("alpha", {"answer": "A"}, ttl=10)
    _ = await cache.get("alpha")

    entry = list(cache._cache.values())[0]
    created_at = entry.created_at
    last_accessed = entry.last_accessed

    cache.save()

    cache_loaded = SemanticCache(
        similarity_threshold=0.8,
        ttl=10,
        persist_path=str(cache_path),
        embedding_model=DummyEmbedder(),
        namespace="tenant-1",
    )

    entry_loaded = list(cache_loaded._cache.values())[0]
    assert entry_loaded.created_at == pytest.approx(created_at)
    assert entry_loaded.last_accessed == pytest.approx(last_accessed)

    _key, cached_query, similarity = await cache_loaded.find_similar("beta")
    assert cached_query == "alpha"
    assert similarity >= 0.8
