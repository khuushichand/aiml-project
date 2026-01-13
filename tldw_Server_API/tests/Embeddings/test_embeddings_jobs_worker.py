import asyncio

import pytest

from tldw_Server_API.app.core.Embeddings.ChromaDB_Library import ChromaDBManager
from tldw_Server_API.app.core.Embeddings.services import jobs_worker
from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.Jobs.migrations import ensure_jobs_tables
from tldw_Server_API.app.core.Jobs.worker_sdk import WorkerConfig, WorkerSDK


@pytest.mark.asyncio
async def test_embeddings_worker_retryable_backoff_from_result(monkeypatch):
    async def fake_generate_embeddings_for_media(**_kwargs):
        return {
            "status": "error",
            "error": "rate limited",
            "retryable": True,
            "backoff_seconds": 12,
        }

    monkeypatch.setattr(jobs_worker, "generate_embeddings_for_media", fake_generate_embeddings_for_media)
    monkeypatch.setattr(jobs_worker, "_resolve_model_provider", lambda *_: ("test-model", "test-provider"))

    job = {
        "job_type": "content_embeddings",
        "payload": {
            "item_id": 123,
            "content": "example content",
        },
    }

    with pytest.raises(jobs_worker.EmbeddingsJobError) as excinfo:
        await jobs_worker._handle_job(job)

    assert excinfo.value.retryable is True
    assert getattr(excinfo.value, "backoff_seconds", None) == 12


@pytest.mark.asyncio
async def test_embeddings_worker_smoke_queue_to_retrieval(monkeypatch, tmp_path):
    db_path = tmp_path / "jobs.db"
    ensure_jobs_tables(db_path)
    jm = JobManager(db_path)

    job = jm.create_job(
        domain="embeddings",
        queue="default",
        job_type="content_embeddings",
        payload={
            "item_id": 321,
            "content": "hello embeddings",
            "title": "Hello",
        },
        owner_user_id="user1",
    )

    embedding_config = {
        "USER_DB_BASE_DIR": str(tmp_path / "chroma"),
        "embedding_config": {"default_model_id": "test-model"},
        "chroma_client_settings": {"backend": "stub", "use_in_memory_stub": True},
    }
    manager = ChromaDBManager(user_id="user1", user_embedding_config=embedding_config)
    collection_name = "user_user1_media_embeddings"

    async def fake_generate_embeddings_for_media(*, media_id, **_kwargs):
        texts = ["hello embeddings"]
        embeddings = [[0.1, 0.2, 0.3]]
        ids = [f"media_{media_id}_chunk_0"]
        metadatas = [
            {
                "media_id": str(media_id),
                "embedding_model": "test-model",
                "embedding_provider": "test-provider",
            }
        ]
        manager.store_in_chroma(collection_name, texts, embeddings, ids, metadatas)
        return {"status": "success", "embedding_count": 1, "chunks_processed": 1}

    monkeypatch.setattr(jobs_worker, "generate_embeddings_for_media", fake_generate_embeddings_for_media)
    monkeypatch.setattr(jobs_worker, "_resolve_model_provider", lambda *_: ("test-model", "test-provider"))

    cfg = WorkerConfig(
        domain="embeddings",
        queue="default",
        worker_id="worker-test",
        lease_seconds=10,
        renew_threshold_seconds=1,
        renew_jitter_seconds=0,
    )
    sdk = WorkerSDK(jm, cfg)

    async def handler(job_row):
        result = await jobs_worker._handle_job(job_row)
        sdk.stop()
        return result

    await asyncio.wait_for(sdk.run(handler=handler), timeout=1)

    stored = jm.get_job(int(job["id"]))
    assert stored["status"] == "completed"
    assert stored["result"]["embedding_count"] == 1

    collection = manager.get_or_create_collection(collection_name)
    data = collection.get(where={"media_id": "321"}, include=["embeddings"])
    assert data.get("ids")
    assert len(data.get("embeddings") or []) == 1
