import pytest

from tldw_Server_API.app.core.RAG.rag_service import semantic_cache


pytestmark = pytest.mark.unit


def test_shared_cache_anchors_relative_persist_path(tmp_path, monkeypatch):


    base_dir = tmp_path / "cache_root"
    base_dir.mkdir()
    monkeypatch.setenv("RAG_SEMANTIC_CACHE_DIR", str(base_dir))
    monkeypatch.delenv("RAG_CACHE_DIR", raising=False)
    monkeypatch.setattr(semantic_cache, "_DEFAULT_CACHE_DIR", None)
    semantic_cache._SHARED_CACHES.clear()

    cache = semantic_cache.get_shared_cache(
        cache_cls=semantic_cache.SemanticCache,
        similarity_threshold=0.9,
        ttl=5,
        max_size=10,
        persist_path="relative_cache.json",
        namespace="tenant",
    )

    expected_path = (base_dir / "relative_cache.json").resolve()
    assert cache.persist_path == str(expected_path)


def test_shared_cache_rejects_absolute_persist_path_outside_base(tmp_path, monkeypatch):


    base_dir = tmp_path / "cache_root"
    base_dir.mkdir()
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    persist_path = outside_dir / "cache.json"
    monkeypatch.setenv("RAG_SEMANTIC_CACHE_DIR", str(base_dir))
    monkeypatch.delenv("RAG_CACHE_DIR", raising=False)
    monkeypatch.setattr(semantic_cache, "_DEFAULT_CACHE_DIR", None)
    semantic_cache._SHARED_CACHES.clear()

    cache = semantic_cache.get_shared_cache(
        cache_cls=semantic_cache.SemanticCache,
        similarity_threshold=0.91,
        ttl=5,
        max_size=10,
        persist_path=str(persist_path),
        namespace="tenant",
    )

    expected_path = (base_dir / "semantic_cache_tenant.json").resolve()
    assert cache.persist_path == str(expected_path)
