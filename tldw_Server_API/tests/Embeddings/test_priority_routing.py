import asyncio
import json

import pytest

from tldw_Server_API.app.core.Embeddings.workers.chunking_worker import ChunkingWorker
from tldw_Server_API.app.core.Embeddings.workers.embedding_worker import EmbeddingWorker, EmbeddingWorkerConfig
from tldw_Server_API.app.core.Embeddings.workers.base_worker import WorkerConfig
from tldw_Server_API.app.core.Embeddings.queue_schemas import ChunkingMessage, ChunkingConfig, ChunkData, EmbeddingMessage, EmbeddingData, StorageMessage


class FakeRedisPR:
    def __init__(self):
        self.writes = []  # list[(stream, fields)]
        self.kv = {}

    async def xadd(self, stream, fields):
        self.writes.append((stream, dict(fields)))
        return f"{len(self.writes)}-0"

    async def get(self, key):
        return self.kv.get(key)

    async def hset(self, key, mapping=None, **kwargs):  # noqa: ARG002
        return 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chunking_routing_priority_and_override(monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_PRIORITY_ENABLED", "true")
    w = ChunkingWorker(WorkerConfig(worker_id="w", worker_type="chunking", queue_name="embeddings:chunking", consumer_group="cg"))
    fr = FakeRedisPR()
    w.redis_client = fr
    msg = ChunkingMessage(
        job_id="j1",
        user_id="u",
        media_id=1,
        priority=80,  # high
        user_tier="free",
        content="hello world",
        content_type="text",
        chunking_config=ChunkingConfig(),
        source_metadata={}
    )
    # Process to produce an EmbeddingMessage then _send_to_next_stage
    out = await w.process_message(msg)
    assert isinstance(out, EmbeddingMessage)
    await w._send_to_next_stage(out)
    assert fr.writes, "no writes"
    stream, _ = fr.writes[-1]
    assert stream.endswith(":embedding:high")

    # Override to low
    fr.kv[f"embeddings:priority:override:{out.job_id}"] = "low"
    await w._send_to_next_stage(out)
    stream2, _ = fr.writes[-1]
    assert stream2.endswith(":embedding:low")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_embedding_routing_priority(monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_PRIORITY_ENABLED", "true")
    ew = EmbeddingWorker(EmbeddingWorkerConfig(worker_id="w2", worker_type="embedding", queue_name="embeddings:embedding", consumer_group="cg"))
    fr = FakeRedisPR()
    ew.redis_client = fr
    # Build a minimal StorageMessage
    emb = EmbeddingData(chunk_id="c1", embedding=[0.1, 0.2], model_used="m", dimensions=2, metadata={})
    sm = StorageMessage(
        job_id="j2",
        user_id="u",
        media_id=1,
        priority=10,  # low
        user_tier="free",
        embeddings=[emb],
        collection_name="col",
        total_chunks=1,
        processing_time_ms=1,
        metadata={}
    )
    await ew._send_to_next_stage(sm)
    stream, _ = fr.writes[-1]
    assert stream.endswith(":storage:low")
