import asyncio
import types

import pytest

from tldw_Server_API.app.core.Metrics import get_metrics_registry

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


class _HYDEEmbeddingWorker(EmbeddingWorker):
    def __init__(self, cfg: EmbeddingWorkerConfig):
        super().__init__(cfg)
        self._calls = []

    async def _generate_embeddings(self, texts, model_config, model_provider):
        # Return a deterministic vector per text length for test simplicity
        self._calls.append(list(texts))
        outs = []
        for t in texts:
            # vector of length 3 with simple values
            outs.append([len(t) % 3, (len(t) + 1) % 3, (len(t) + 2) % 3])
        return outs


@pytest.mark.unit
def test_hyde_option_a_inlines_generation(monkeypatch):
    # Patch settings inside the module under test
    import tldw_Server_API.app.core.Embeddings.workers.embedding_worker as emb_mod
    registry = get_metrics_registry()
    registry.values.pop("hyde_questions_generated_total", None)
    registry.values.pop("hyde_generation_failures_total", None)
    # Enable HYDE with N=2 and fixed provider/model
    emb_mod.settings["HYDE_ENABLED"] = True
    emb_mod.settings["HYDE_QUESTIONS_PER_CHUNK"] = 2
    emb_mod.settings["HYDE_PROVIDER"] = "openai"
    emb_mod.settings["HYDE_MODEL"] = "gpt-4o-mini"
    emb_mod.settings["HYDE_TEMPERATURE"] = 0.1
    emb_mod.settings["HYDE_MAX_TOKENS"] = 64
    emb_mod.settings["HYDE_LANGUAGE"] = "en"
    emb_mod.settings["HYDE_PROMPT_VERSION"] = 1

    # Patch hyde.generate_questions to return two questions
    def _fake_generate_questions(text, n, provider=None, model=None, **kwargs):
        return [
            "What is the main idea of this chunk?",
            "How does this section support the thesis?",
        ][:n]

    monkeypatch.setattr(emb_mod, "generate_questions", _fake_generate_questions)

    cfg = EmbeddingWorkerConfig(
        worker_id="embedding-test",
        worker_type="embedding",
        redis_url="redis://localhost:6379",
        queue_name="embeddings:embedding",
        consumer_group="embedding-workers",
        enable_caching=False,
    )
    w = _HYDEEmbeddingWorker(cfg)
    w.redis_client = _FakeRedis()

    msg = EmbeddingMessage(
        job_id="job-hyde-1",
        user_id="u",
        media_id=1,
        chunks=[ChunkData(chunk_id="c1", content="Short content.", metadata={"content_hash": "abcd"}, start_index=0, end_index=6, sequence_number=0)],
        embedding_model_config={},
        model_provider="huggingface",
    )

    out = asyncio.run(w.process_message(msg))
    assert out is not None
    # Expect 1 base embedding + 2 HYDE embeddings
    assert len(out.embeddings) == 3
    # HYDE IDs carry the q: suffix
    hyde_ids = [e.chunk_id for e in out.embeddings if ":q:" in e.chunk_id]
    assert len(hyde_ids) == 2
    # HYDE metadata fields present
    for e in out.embeddings:
        if ":q:" in e.chunk_id:
            assert e.metadata.get("kind") == "hyde_q"
            assert e.metadata.get("parent_chunk_id") == "c1"
            assert "question_hash" in e.metadata
            assert e.metadata.get("hyde_prompt_version") == 1
    stats = registry.get_metric_stats(
        "hyde_questions_generated_total",
        labels={"provider": "openai", "model": "gpt-4o-mini", "source": "worker"},
    )
    assert stats and stats.get("sum") == 2
    assert not registry.get_metric_stats("hyde_generation_failures_total")
