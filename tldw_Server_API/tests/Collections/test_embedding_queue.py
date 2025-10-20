import asyncio
import pytest

from tldw_Server_API.app.core.Collections import embedding_queue
from tldw_Server_API.app.core.Collections.embedding_queue import enqueue_embeddings_job_for_item


@pytest.mark.asyncio
async def test_enqueue_embeddings_job_uses_manager(monkeypatch):
    captured = {}

    class FakeManager:
        def __init__(self, config):
            captured["config"] = config

        async def initialize(self):
            captured["initialized"] = True

        async def create_job(self, **kwargs):
            captured["job_kwargs"] = kwargs

        async def close(self):
            captured["closed"] = True

    monkeypatch.setenv("TEST_MODE", "0")
    monkeypatch.setattr(embedding_queue, "_redis_url", lambda: "redis://localhost:6389/2")
    monkeypatch.setattr(embedding_queue, "EmbeddingJobManager", FakeManager)

    await enqueue_embeddings_job_for_item(
        user_id=123,
        item_id=456,
        content="Example content to embed.",
        metadata={"origin": "reading"},
    )

    assert captured["config"].redis_url.endswith("6389/2")
    assert captured["initialized"] is True
    assert captured["closed"] is True
    job_kwargs = captured["job_kwargs"]
    assert job_kwargs["media_id"] == 456
    assert job_kwargs["user_id"] == "123"
    assert "content" in job_kwargs and "Example content" in job_kwargs["content"]
    assert job_kwargs["metadata"]["origin"] == "reading"


@pytest.mark.asyncio
async def test_enqueue_embeddings_skips_empty_content(monkeypatch):
    called = {}

    class FakeManager:
        def __init__(self, config):
            called["config"] = config

        async def initialize(self):
            called["initialized"] = True

        async def create_job(self, **kwargs):
            called["job_kwargs"] = kwargs

        async def close(self):
            called["closed"] = True

    monkeypatch.setenv("TEST_MODE", "0")
    monkeypatch.setattr(embedding_queue, "EmbeddingJobManager", FakeManager)

    await enqueue_embeddings_job_for_item(
        user_id=1,
        item_id=2,
        content="   ",
        metadata={"origin": "reading"},
    )

    assert "initialized" not in called
