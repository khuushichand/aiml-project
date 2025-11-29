from tldw_Server_API.app.core.RAG.rag_service.semantic_cache import SemanticCache


def test_semantic_cache_stats_include_namespace():
    cache = SemanticCache(similarity_threshold=0.9, ttl=10, namespace="tenant-123")
    stats = cache.get_stats()
    assert stats.get("namespace") == "tenant-123"

