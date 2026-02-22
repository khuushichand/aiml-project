import asyncio
import contextlib

import pytest

from tldw_Server_API.app.core.Embeddings import redis_pipeline
from tldw_Server_API.app.core.Embeddings.services import redis_worker


pytestmark = pytest.mark.integration


def test_redis_worker_chunking_roundtrip_real_redis(redis_client, monkeypatch):
    streams = redis_pipeline.load_queues()
    redis_client.flush()

    class _SharedClient:
        def __init__(self, client):
            self._client = client

        def __getattr__(self, name):
            return getattr(self._client, name)

        async def close(self):
            return None

    shared_client = _SharedClient(redis_client.client)

    async def _fake_create_async_redis_client(**_kwargs):
        return shared_client

    async def _fake_chunking(*_args, **_kwargs):
        return {
            "chunks_path": "/tmp/embeddings_chunks.json",  # nosec B108
            "chunks_processed": 1,
            "total_chunks": 1,
        }, False

    monkeypatch.setattr(redis_worker, "create_async_redis_client", _fake_create_async_redis_client)
    monkeypatch.setattr(redis_worker.jobs_worker, "_handle_chunking_job", _fake_chunking)
    monkeypatch.setattr(redis_worker.jobs_worker, "_update_root_progress", lambda *_a, **_k: None)
    monkeypatch.setattr(redis_worker.jobs_worker, "_update_root_job", lambda *_a, **_k: None)
    monkeypatch.setattr(redis_worker.jobs_worker, "_update_root_result", lambda *_a, **_k: None)
    monkeypatch.setattr(redis_worker.jobs_worker, "_resolve_model_provider", lambda *_a: ("model", "provider"))
    monkeypatch.setenv("EMBEDDINGS_REDIS_POLL_INTERVAL_MS", "50")

    payload = {
        "media_id": 101,
        "user_id": "redis-worker-test",
        "root_job_uuid": "root-redis-worker-test",
        "chunk_size": 1000,
        "chunk_overlap": 200,
    }
    redis_client.run(redis_client.xadd(streams.streams["chunking"], payload))

    async def _run_worker_once():
        stop_event = asyncio.Event()
        task = asyncio.create_task(redis_worker._worker_loop("chunking", "test-worker", stop_event))
        try:
            for _ in range(50):
                if await redis_client.xlen(streams.streams["embedding"]) > 0:
                    break
                await asyncio.sleep(0.05)
        finally:
            stop_event.set()
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(task, timeout=1)
        if not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        return await redis_client.xlen(streams.streams["embedding"])

    embedding_len = redis_client.run(_run_worker_once())
    assert embedding_len == 1
