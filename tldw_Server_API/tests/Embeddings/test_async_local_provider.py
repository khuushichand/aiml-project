import asyncio
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from tldw_Server_API.app.core.Embeddings.async_embeddings import AsyncLocalProvider


@pytest.mark.asyncio
async def test_async_local_provider_loads_once(monkeypatch):
    load_count = {"count": 0}

    class DummySentenceTransformer:
        def __init__(self, model_name):
            _ = model_name
            load_count["count"] += 1

        def encode(self, text, convert_to_tensor=False):

            _ = (text, convert_to_tensor)
            return np.array([0.1, 0.2], dtype=np.float32)

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=DummySentenceTransformer),
    )

    provider = AsyncLocalProvider()

    await asyncio.gather(
        provider.create_embedding("a", model="mini"),
        provider.create_embedding("b", model="mini"),
    )

    assert load_count["count"] == 1


@pytest.mark.asyncio
async def test_async_local_provider_eviction_calls_cpu_cleanup():
    class DummyModel:
        def __init__(self):
            self.cpu_called = False

        def cpu(self):
            self.cpu_called = True

    provider = AsyncLocalProvider(max_models_in_memory=1, model_ttl_seconds=0)
    model_old = DummyModel()
    model_new = DummyModel()

    # Seed two models with different last-used timestamps
    provider.models = {"old": model_old, "new": model_new}
    provider.model_last_used = {"old": 1.0, "new": 2.0}
    provider.model_in_use = {"old": 0, "new": 0}

    await provider._evict_if_needed()

    assert "old" not in provider.models
    assert "new" in provider.models
    assert model_old.cpu_called is True


@pytest.mark.asyncio
async def test_async_local_provider_eviction_keeps_single_loaded_model():
    class DummyModel:
        def __init__(self):
            self.cpu_called = False

        def cpu(self):
            self.cpu_called = True

    provider = AsyncLocalProvider(max_models_in_memory=1, model_ttl_seconds=0)
    only = DummyModel()
    provider.models = {"only": only}
    provider.model_last_used = {"only": 1.0}
    provider.model_in_use = {"only": 0}

    await provider._evict_if_needed()

    assert "only" in provider.models
    assert only.cpu_called is False
