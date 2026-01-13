from pathlib import Path

from tldw_Server_API.app.core.Embeddings import redis_pipeline
from tldw_Server_API.app.core.Embeddings.jobs_adapter import EmbeddingsJobsAdapter
from tldw_Server_API.app.core.Infrastructure.redis_factory import InMemorySyncRedis
from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.Jobs.migrations import ensure_jobs_tables


def _setup_jobs_db(monkeypatch, tmp_path: Path) -> Path:
    db_path = tmp_path / "jobs.db"
    ensure_jobs_tables(db_path)
    monkeypatch.setenv("JOBS_DB_PATH", str(db_path))
    monkeypatch.delenv("JOBS_DB_URL", raising=False)
    monkeypatch.setenv("EMBEDDINGS_JOBS_QUEUE", "default")
    monkeypatch.setenv("EMBEDDINGS_ROOT_JOBS_QUEUE", "low")
    monkeypatch.setenv("EMBEDDINGS_REDIS_ALLOW_STUB", "1")
    return db_path


def test_embeddings_jobs_adapter_idempotent_root_and_stage(monkeypatch, tmp_path):
    db_path = _setup_jobs_db(monkeypatch, tmp_path)
    stub = InMemorySyncRedis(decode_responses=True)
    monkeypatch.setattr(redis_pipeline, "create_sync_redis_client", lambda **_kwargs: stub)
    adapter = EmbeddingsJobsAdapter()

    job1 = adapter.create_job(
        user_id="user1",
        media_id=101,
        embedding_model="model-a",
        embedding_provider="provider-a",
        chunk_size=1000,
        chunk_overlap=200,
        request_source="test",
        force_regenerate=False,
        stage="chunking",
        embedding_priority=50,
    )
    job2 = adapter.create_job(
        user_id="user1",
        media_id=101,
        embedding_model="model-a",
        embedding_provider="provider-a",
        chunk_size=1000,
        chunk_overlap=200,
        request_source="test",
        force_regenerate=False,
        stage="chunking",
        embedding_priority=50,
    )

    assert str(job1.get("uuid")) == str(job2.get("uuid"))

    jm = JobManager(db_path)
    jobs = jm.list_jobs(domain="embeddings", owner_user_id="user1", limit=20)
    root_jobs = [row for row in jobs if row.get("job_type") == "embeddings_pipeline"]
    stage_jobs = [row for row in jobs if row.get("job_type") != "embeddings_pipeline"]

    assert len(root_jobs) == 1
    assert len(stage_jobs) == 0
    assert stub.xlen(redis_pipeline.stream_name("chunking")) == 1


def test_embeddings_jobs_adapter_status_tracks_stage(monkeypatch, tmp_path):
    db_path = _setup_jobs_db(monkeypatch, tmp_path)
    stub = InMemorySyncRedis(decode_responses=True)
    monkeypatch.setattr(redis_pipeline, "create_sync_redis_client", lambda **_kwargs: stub)
    adapter = EmbeddingsJobsAdapter()

    root = adapter.create_job(
        user_id="user1",
        media_id=202,
        embedding_model="model-b",
        embedding_provider="provider-b",
        chunk_size=1000,
        chunk_overlap=200,
        request_source="test",
        force_regenerate=False,
        stage="chunking",
        embedding_priority=50,
    )

    root_id = str(root.get("uuid") or root.get("id"))
    queued = adapter.get_job(root_id, "user1")
    assert queued is not None
    assert queued.get("status") == "queued"

    jm = JobManager(db_path)
    jm.update_job_progress(int(root["id"]), progress_percent=10.0, progress_message="chunking started")

    processing = adapter.get_job(root_id, "user1")
    assert processing is not None
    assert processing.get("status") == "processing"


def test_embeddings_jobs_adapter_exposes_progress(monkeypatch, tmp_path):
    db_path = _setup_jobs_db(monkeypatch, tmp_path)
    monkeypatch.setenv("EMBEDDINGS_JOBS_EXPOSE_PROGRESS", "1")
    adapter = EmbeddingsJobsAdapter()

    root = adapter.create_job(
        user_id="user1",
        media_id=303,
        embedding_model="model-c",
        embedding_provider="provider-c",
        chunk_size=1000,
        chunk_overlap=200,
        request_source="test",
        force_regenerate=False,
        stage="chunking",
        embedding_priority=50,
    )

    jm = JobManager(db_path)
    jm.update_job_progress(int(root["id"]), progress_percent=33.0)

    rec = adapter.get_job(str(root.get("uuid") or root.get("id")), "user1")
    assert rec is not None
    assert rec.get("progress_percent") == 33.0
