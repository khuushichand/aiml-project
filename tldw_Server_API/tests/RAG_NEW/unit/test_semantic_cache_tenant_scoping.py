import pytest

from tldw_Server_API.app.core.RAG.rag_service import semantic_cache
from tldw_Server_API.app.core.RAG.rag_service.semantic_cache import SemanticCache

pytestmark = pytest.mark.unit


def test_semantic_cache_stats_include_namespace():


    cache = SemanticCache(similarity_threshold=0.9, ttl=10, namespace="tenant-123")
    stats = cache.get_stats()
    assert stats.get("namespace") == "tenant-123"


def test_shared_cache_instances_are_isolated_by_namespace(tmp_path, monkeypatch):
    cache_root = tmp_path / "cache_root"
    cache_root.mkdir()
    monkeypatch.setenv("RAG_SEMANTIC_CACHE_DIR", str(cache_root))
    monkeypatch.delenv("RAG_CACHE_DIR", raising=False)
    monkeypatch.setattr(semantic_cache, "_DEFAULT_CACHE_DIR", None)
    semantic_cache._SHARED_CACHES.clear()

    cache_tenant_a = semantic_cache.get_shared_cache(
        cache_cls=SemanticCache,
        similarity_threshold=0.9,
        ttl=60,
        max_size=10,
        namespace="tenant-a",
    )
    cache_tenant_b = semantic_cache.get_shared_cache(
        cache_cls=SemanticCache,
        similarity_threshold=0.9,
        ttl=60,
        max_size=10,
        namespace="tenant-b",
    )
    cache_tenant_a_again = semantic_cache.get_shared_cache(
        cache_cls=SemanticCache,
        similarity_threshold=0.9,
        ttl=60,
        max_size=10,
        namespace="tenant-a",
    )

    assert cache_tenant_a is cache_tenant_a_again
    assert cache_tenant_a is not cache_tenant_b


def test_clear_shared_caches_respects_namespace_scope(tmp_path, monkeypatch):
    cache_root = tmp_path / "cache_root"
    cache_root.mkdir()
    monkeypatch.setenv("RAG_SEMANTIC_CACHE_DIR", str(cache_root))
    monkeypatch.delenv("RAG_CACHE_DIR", raising=False)
    monkeypatch.setattr(semantic_cache, "_DEFAULT_CACHE_DIR", None)
    semantic_cache._SHARED_CACHES.clear()

    cache_tenant_a = semantic_cache.get_shared_cache(
        cache_cls=SemanticCache,
        similarity_threshold=0.9,
        ttl=60,
        max_size=10,
        namespace="tenant-a",
    )
    cache_tenant_b = semantic_cache.get_shared_cache(
        cache_cls=SemanticCache,
        similarity_threshold=0.9,
        ttl=60,
        max_size=10,
        namespace="tenant-b",
    )

    cache_tenant_a._cache["a"] = object()
    cache_tenant_b._cache["b"] = object()

    cleared = semantic_cache.clear_shared_caches(namespace="tenant-a")

    assert cleared == 1
    assert cache_tenant_a.get_stats()["size"] == 0
    assert cache_tenant_b.get_stats()["size"] == 1
