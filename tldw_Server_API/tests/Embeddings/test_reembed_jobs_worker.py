import asyncio
import os
import pytest

from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.Embeddings.services import reembed_worker


@pytest.mark.integration
def test_reembed_worker_expands_to_embedding_stream(monkeypatch, redis_client, tmp_path):
    # Patch chunk fetch to avoid DB dependencies
    monkeypatch.setattr(reembed_worker, "_fetch_chunks", lambda db, media_id: [("hello world", 0, 11), ("two", 12, 15)])
    monkeypatch.setattr(reembed_worker, "_dev_shortcuts_enabled", lambda: False)
    monkeypatch.setenv("EMBEDDINGS_REDIS_URL", redis_client.url)

    # Prepare Jobs DB (SQLite file in temp dir for cleanup)
    db_path = tmp_path / "test_jobs_reembed_e2e.db"
    monkeypatch.setenv("JOBS_DB_PATH", str(db_path))

    # Speed up worker polling in test
    monkeypatch.setenv("JOBS_POLL_INTERVAL_SECONDS", "0.05")
    # Allow 'reembed' queue for embeddings domain
    monkeypatch.setenv("JOBS_ALLOWED_QUEUES_EMBEDDINGS", "reembed")
    jm = JobManager()
    row = jm.create_job(
        domain="embeddings",
        queue=os.getenv("REEMBED_JOB_QUEUE", "reembed"),
        job_type="expand_reembed",
        payload={"user_id": "1", "media_id": 123},
        owner_user_id="1",
        priority=5,
    )
    assert row and row.get("id")

    # Run the worker briefly
    async def _run_worker_until_stream():
        stop = asyncio.Event()
        task = asyncio.create_task(reembed_worker.run(stop))
        try:
            loop = asyncio.get_running_loop()
            deadline = loop.time() + 2.0
            backoff = 0.02
            max_backoff = 0.2
            while True:
                out = await redis_client.xrange("embeddings:embedding", "-", "+", count=10)
                if isinstance(out, list) and len(out) >= 1 and isinstance(out[0], (list, tuple)):
                    return out
                if loop.time() >= deadline:
                    raise AssertionError("Timed out waiting for embeddings stream entry")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)
        finally:
            stop.set()
            try:
                await asyncio.wait_for(task, timeout=1.0)
            except asyncio.TimeoutError:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass  # Expected when cancelling
            except asyncio.CancelledError:
                pass  # Expected when cancelling

    res = redis_client.run(_run_worker_until_stream())
    assert isinstance(res, list) and len(res) >= 1
    # Fields should include job_id
    entry_id, fields = res[0]
    assert "job_id" in (fields or {})
