import asyncio
import pytest

from tldw_Server_API.app.core.Collections import embedding_queue
from tldw_Server_API.app.core.Collections.embedding_queue import enqueue_embeddings_job_for_item


@pytest.mark.asyncio
async def test_enqueue_embeddings_job_uses_manager(monkeypatch):
    captured = {}

    class FakeManager:
        def create_job(self, **kwargs):
            captured["job_kwargs"] = kwargs

    monkeypatch.setenv("TEST_MODE", "0")
    monkeypatch.setattr(embedding_queue, "JobManager", FakeManager)

    await enqueue_embeddings_job_for_item(
        user_id=123,
        item_id=456,
        content="Example content to embed.",
        metadata={"origin": "reading"},
    )

    job_kwargs = captured["job_kwargs"]
    assert job_kwargs["domain"] == "embeddings"
    assert job_kwargs["queue"] == "default"
    assert job_kwargs["job_type"] == "content_embeddings"
    assert job_kwargs["owner_user_id"] == "123"
    assert job_kwargs["payload"]["item_id"] == 456
    assert "content" in job_kwargs["payload"] and "Example content" in job_kwargs["payload"]["content"]
    assert job_kwargs["payload"]["metadata"]["origin"] == "reading"


@pytest.mark.asyncio
async def test_enqueue_embeddings_skips_empty_content(monkeypatch):
    called = {}

    class FakeManager:
        def create_job(self, **kwargs):
            called["job_kwargs"] = kwargs

    monkeypatch.setenv("TEST_MODE", "0")
    monkeypatch.setattr(embedding_queue, "JobManager", FakeManager)

    await enqueue_embeddings_job_for_item(
        user_id=1,
        item_id=2,
        content="   ",
        metadata={"origin": "reading"},
    )

    assert "initialized" not in called
