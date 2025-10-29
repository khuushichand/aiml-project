import asyncio
import time
from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.Jobs.migrations import ensure_jobs_tables
from tldw_Server_API.app.core.Jobs.manager import JobManager


@pytest.mark.asyncio
async def test_core_worker_honors_mid_processing_cancellation(monkeypatch, tmp_path):
    # Prepare isolated jobs DB
    jobs_db = tmp_path / "jobs.db"
    ensure_jobs_tables(jobs_db)
    jm = JobManager(jobs_db)

    # Build a fake ChatbookService with minimal surface
    from tldw_Server_API.app.core.Chatbooks.chatbook_models import ExportStatus

    class FakeExportJob:
        def __init__(self, jid: str):
            self.job_id = jid
            self.status = ExportStatus.PENDING
            self.started_at = None
            self.completed_at = None
            self.output_path = None
            self.file_size_bytes = None
            self.expires_at = None
            self.download_url = None
            self.error_message = None

    class FakeChatbookService:
        def __init__(self, user_id, db, **kwargs):
            self._jobs = {}
        def _get_export_job(self, jid: str):
            return self._jobs.get(jid)
        def _save_export_job(self, ej):
            self._jobs[ej.job_id] = ej
        def _build_download_url(self, job_id, _exp):
            return f"http://test/{job_id}"
        async def _create_chatbook_sync_wrapper(self, **kwargs):
            # Simulate long work
            await asyncio.sleep(0.5)
            return True, None, "/tmp/fake.zip"

    # Patch the worker to use our FakeChatbookService and a JM bound to our DB
    import tldw_Server_API.app.services.core_jobs_worker as worker

    class JMProxy:
        def __init__(self):
            self._jm = jm
        def __getattr__(self, name):
            return getattr(self._jm, name)

    monkeypatch.setattr(worker, "JobManager", JMProxy)
    monkeypatch.setattr(worker, "ChatbookService", FakeChatbookService)

    # Seed a Chatbooks export job state the worker expects
    svc = FakeChatbookService("1", None)
    ej = FakeExportJob("cb-1")
    svc._save_export_job(ej)

    # Ensure the worker built in module will find the ej when it constructs svc anew
    # by monkeypatching _get_export_job to always refer to our seeded state
    def _fake_get_export_job(self, jid):
        # Avoid recursion by reading from the seeded instance dictionary directly
        return svc._jobs.get(jid)
    monkeypatch.setattr(FakeChatbookService, "_get_export_job", _fake_get_export_job)

    # Create a job and start the worker
    job = jm.create_job(
        domain="chatbooks",
        queue="default",
        job_type="export",
        payload={"action": "export", "chatbooks_job_id": "cb-1", "user_id": "1"},
        owner_user_id="1",
    )

    stop_event = asyncio.Event()
    run_task = asyncio.create_task(worker.run_chatbooks_core_jobs_worker(stop_event))

    # Allow worker to acquire and start processing
    await asyncio.sleep(0.2)
    # Request cancellation mid-flight
    jm.cancel_job(int(job["id"]))

    # Wait for worker to process
    await asyncio.sleep(0.6)
    stop_event.set()
    # Prefer graceful stop; if still running after timeout, cancel
    try:
        await asyncio.wait_for(run_task, timeout=2.0)
    except asyncio.TimeoutError:
        run_task.cancel()
        try:
            await run_task
        except asyncio.CancelledError:
            pass

    # Assert job was terminally cancelled
    jr = jm.get_job(int(job["id"]))
    assert jr["status"] == "cancelled"
    # Assert Chatbooks export job reflected CANCELLED (allow brief propagation)
    deadline = asyncio.get_event_loop().time() + 3.0
    while True:
        ej2 = svc._get_export_job("cb-1")
        if ej2 and getattr(ej2.status, "name", str(ej2.status)) == "CANCELLED":
            break
        if asyncio.get_event_loop().time() > deadline:
            break
        await asyncio.sleep(0.05)
    assert ej2.status.name == "CANCELLED"
