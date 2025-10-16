import argparse
import asyncio
from types import SimpleNamespace

import pytest

from Helper_Scripts import hyde_backfill
from tldw_Server_API.app.core.Metrics import get_metrics_registry


class _DummySettings(dict):
    def get(self, key, default=None):
        return super().get(key, default)


class _FakeAdapter:
    def __init__(self):
        self.config = SimpleNamespace(embedding_dim=3, store_type="chromadb")
        self.upserts = []
        self._pages_returned = 0

    async def initialize(self):
        return None

    async def list_vectors_paginated(self, collection_name, limit, offset, filter):
        if self._pages_returned:
            return {"items": []}
        self._pages_returned += 1
        return {
            "items": [
                {
                    "id": "chunk-1",
                    "content": "Chunk content for embedding.",
                    "metadata": {
                        "chunk_id": "chunk-1",
                        "embedder_name": "huggingface",
                        "embedder_version": "test-model",
                        "language": "english",
                    },
                }
            ]
        }

    async def upsert_vectors(self, collection_name, ids, vectors, documents, metadatas):
        self.upserts.append((collection_name, list(ids), list(vectors), list(documents), list(metadatas)))
        return None


@pytest.mark.unit
def test_hyde_backfill_embeds_real_vectors(monkeypatch):
    adapter = _FakeAdapter()
    registry = get_metrics_registry()
    registry.values.pop("hyde_questions_generated_total", None)
    registry.values.pop("hyde_generation_failures_total", None)
    registry.values.pop("hyde_vectors_written_total", None)

    # Patch settings to a lightweight dict
    dummy_settings = _DummySettings(
        {
            "SINGLE_USER_FIXED_ID": "1",
            "HYDE_QUESTIONS_PER_CHUNK": 2,
            "HYDE_PROVIDER": "openai",
            "HYDE_MODEL": "gpt-hyde",
            "HYDE_TEMPERATURE": 0.0,
            "HYDE_MAX_TOKENS": 32,
            "HYDE_LANGUAGE": "auto",
            "HYDE_PROMPT_VERSION": 1,
            "EMBEDDINGS_MODEL_STORAGE_DIR": "./models/embedding_models_data/",
            "EMBEDDINGS_DEFAULT_PROVIDER": "huggingface",
            "EMBEDDINGS_DEFAULT_MODEL_ID": "test-model",
        }
    )
    monkeypatch.setattr("tldw_Server_API.app.core.config.settings", dummy_settings, raising=False)

    # Patch vector store factory to return fake adapter
    monkeypatch.setattr(
        "tldw_Server_API.app.core.RAG.rag_service.vector_stores.factory.VectorStoreFactory.create_from_settings",
        lambda _settings, user_id=None: adapter,
    )

    # Patch HYDE question generation and embedding creation
    def _fake_questions(text, n, **kwargs):
        return [f"Question {i}" for i in range(1, n + 1)]

    monkeypatch.setattr("tldw_Server_API.app.core.Embeddings.hyde.generate_questions", _fake_questions)

    def _fake_create(texts, app_config, model_id_override):
        # Return deterministic vectors with non-zero values
        return [[float(idx + 1), 0.1 * (idx + 1), 0.01 * (idx + 1)] for idx, _ in enumerate(texts)]

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create.create_embeddings_batch",
        _fake_create,
    )

    args = argparse.Namespace(user_id="1", collection="demo", page_size=10, dry_run=False)
    rc = asyncio.run(hyde_backfill._run(args))

    assert rc == 0
    assert adapter.upserts, "Expected HYDE vectors to be written"
    _, ids, vectors, documents, metadatas = adapter.upserts[0]
    assert all(vec[0] != 0.0 for vec in vectors), "Vectors should not be zero placeholders"
    assert all(":q:" in vid for vid in ids)
    assert len(documents) == len(vectors) == len(metadatas)
    for meta in metadatas:
        assert meta.get("kind") == "hyde_q"
        assert meta.get("question_hash"), "question_hash should be recorded"
    stats = registry.get_metric_stats(
        "hyde_questions_generated_total",
        labels={"provider": "openai", "model": "gpt-hyde", "source": "backfill"},
    )
    assert stats and stats.get("sum") == 2
    vector_stats = registry.get_metric_stats("hyde_vectors_written_total", labels={"store": "chromadb"})
    assert vector_stats and vector_stats.get("sum") == 2
    assert not registry.get_metric_stats("hyde_generation_failures_total")
