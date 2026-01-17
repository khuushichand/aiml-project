import pytest


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_media_ingest_worker_honors_cancel_before_processing(monkeypatch, tmp_path):
    monkeypatch.setenv("JOBS_DB_PATH", str(tmp_path / "jobs.db"))
    monkeypatch.delenv("JOBS_DB_URL", raising=False)

    from tldw_Server_API.app.core.Jobs.manager import JobManager
    import tldw_Server_API.app.services.media_ingest_jobs_worker as worker

    jm = JobManager()
    payload = {
        "batch_id": "batch-1",
        "media_type": "document",
        "source": str(tmp_path / "cancelled.txt"),
        "source_kind": "file",
        "input_ref": "cancelled.txt",
        "temp_dir": str(tmp_path / "staging"),
        "cleanup_temp_dir": False,
        "options": {"media_type": "document"},
    }
    row = jm.create_job(
        domain="media_ingest",
        queue="default",
        job_type="media_ingest_item",
        payload=payload,
        owner_user_id="1",
    )
    job_id = int(row.get("id"))
    jm.cancel_job(job_id, reason="test cancel")

    def _boom(*_args, **_kwargs):
        raise AssertionError("processing called despite cancellation")

    monkeypatch.setattr(worker, "process_batch_media", _boom, raising=True)
    monkeypatch.setattr(worker, "process_document_like_item", _boom, raising=True)

    job = jm.get_job(job_id)
    progress = worker._ProgressState()
    result = await worker._handle_job(job, jm, progress)

    assert result == {}
    updated = jm.get_job(job_id)
    assert updated is not None
    assert updated.get("status") == "cancelled"


@pytest.mark.asyncio
async def test_media_ingest_worker_updates_progress_fields(monkeypatch, tmp_path):
    monkeypatch.setenv("JOBS_DB_PATH", str(tmp_path / "jobs.db"))
    monkeypatch.delenv("JOBS_DB_URL", raising=False)

    from tldw_Server_API.app.core.Jobs.manager import JobManager
    import tldw_Server_API.app.services.media_ingest_jobs_worker as worker

    class _DummyDB:
        def __init__(self, path: str):
            self.db_path_str = path
            self.client_id = "media_ingest_test"

        def close_connection(self):
            return None

    def _fake_create_db(_user_id: str):
        return _DummyDB(str(tmp_path / "media.db"))

    async def _fake_process_document_like_item(**_kwargs):
        return {
            "status": "Success",
            "db_id": 123,
            "media_uuid": "media-uuid-123",
            "warnings": None,
        }

    monkeypatch.setattr(worker, "_create_db", _fake_create_db, raising=True)
    monkeypatch.setattr(worker, "process_document_like_item", _fake_process_document_like_item, raising=True)
    monkeypatch.setattr(worker, "prepare_chunking_options_dict", lambda _form: None, raising=True)

    jm = JobManager()
    payload = {
        "batch_id": "batch-2",
        "media_type": "document",
        "source": str(tmp_path / "doc.txt"),
        "source_kind": "file",
        "input_ref": "doc.txt",
        "options": {"media_type": "document"},
    }
    row = jm.create_job(
        domain="media_ingest",
        queue="default",
        job_type="media_ingest_item",
        payload=payload,
        owner_user_id="1",
    )

    job = jm.get_job(int(row.get("id")))
    progress = worker._ProgressState()
    result = await worker._handle_job(job, jm, progress)

    assert result.get("status") == "Success"
    updated = jm.get_job(int(row.get("id")))
    assert updated is not None
    assert updated.get("progress_message") == "completed"
    assert float(updated.get("progress_percent") or 0.0) >= 100.0
