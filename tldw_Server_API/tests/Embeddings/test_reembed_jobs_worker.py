import asyncio
import os
import pytest

from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.Embeddings.services import reembed_worker


@pytest.mark.integration
def test_reembed_worker_expands_to_embedding_stream(monkeypatch, fake_redis):
    # Patch chunk fetch to avoid DB dependencies
    monkeypatch.setattr(reembed_worker, "_fetch_chunks", lambda db, media_id: [("hello world", 0, 11), ("two", 12, 15)])

    # Prepare Jobs DB (SQLite file in repo Databases/ for simplicity)
    db_path = "Databases/test_jobs_reembed_e2e.db"
    try:
        os.environ["JOBS_DB_PATH"] = db_path
    except Exception:
        pass

    # Speed up worker polling in test
    os.environ["JOBS_POLL_INTERVAL_SECONDS"] = "0.05"
    # Allow 'reembed' queue for embeddings domain
    os.environ["JOBS_ALLOWED_QUEUES_EMBEDDINGS"] = "reembed"
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
    async def _run_worker_brief():
        stop = asyncio.Event()
        task = asyncio.create_task(reembed_worker.run(stop))
        # Allow loop to process at least one cycle
        await asyncio.sleep(0.6)
        stop.set()
        await asyncio.sleep(0.05)
        try:
            task.cancel()
        except Exception:
            pass

    asyncio.run(_run_worker_brief())

    # Verify the embedding stream received entries
    res = asyncio.run(fake_redis.xrange("embeddings:embedding", "-", "+", count=10))
    assert isinstance(res, list) and len(res) >= 1
    # Fields should include job_id
    entry_id, fields = res[0]
    assert "job_id" in (fields or {})
