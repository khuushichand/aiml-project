"""
Unit tests for in-use guard on embeddings model eviction.
"""

import time

import pytest

from tldw_Server_API.app.core.Embeddings.Embeddings_Server import Embeddings_Create as EC


@pytest.mark.unit
def test_evict_lru_skips_in_use_models(monkeypatch):
    """Ensure models marked in-use are not evicted."""
    now = time.time()

    monkeypatch.setattr(EC, "embedding_models", {"model_a": object(), "model_b": object()})
    monkeypatch.setattr(
        EC,
        "model_last_used",
        {"model_a": now - 100, "model_b": now - 100},
    )
    monkeypatch.setattr(EC, "model_memory_usage", {"model_a": 1.0, "model_b": 1.0})
    monkeypatch.setattr(EC, "model_in_use_counts", {"model_a": 1})
    monkeypatch.setattr(EC, "MAX_MODELS_IN_MEMORY", 1)
    monkeypatch.setattr(EC, "MODEL_LRU_TTL_SECONDS", 0)

    EC.evict_lru_models()

    assert "model_a" in EC.embedding_models
    assert "model_b" not in EC.embedding_models
