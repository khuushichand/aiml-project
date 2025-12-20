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
