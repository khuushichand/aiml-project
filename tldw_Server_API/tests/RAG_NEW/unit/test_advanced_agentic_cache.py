import time

import pytest

from tldw_Server_API.app.core.RAG.rag_service.advanced_cache import AdvancedAgenticCache


def test_advanced_agentic_cache_get_set_and_invalidate_prefix():
    cache = AdvancedAgenticCache()

    ns = "ephemeral_chunk"
    key1 = "docA|qhash1"
    key2 = "docA|qhash2"
    val1 = {"v": 1}
    val2 = {"v": 2}

    # Initially empty
    assert cache.get(ns, key1) is None

    # Set and get
    cache.set(ns, key1, val1, ttl_sec=60)
    assert cache.get(ns, key1) == val1

    # Set another key with same prefix
    cache.set(ns, key2, val2, ttl_sec=60)
    assert cache.get(ns, key2) == val2

    # Invalidate by prefix
    removed = cache.invalidate_prefix(ns, "docA|")
    assert removed >= 2
    assert cache.get(ns, key1) is None
    assert cache.get(ns, key2) is None

    # TTL behavior (coarse): set with short TTL and allow expire
    cache.set(ns, "short", {"v": 3}, ttl_sec=1)
    assert cache.get(ns, "short") == {"v": 3}
    time.sleep(1.2)
    assert cache.get(ns, "short") is None
