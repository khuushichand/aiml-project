import os

from tldw_Server_API.app.core.Jobs.migrations import ensure_jobs_tables
from tldw_Server_API.app.core.Jobs.manager import JobManager


def test_enforcement_blocks_stale_worker(monkeypatch, tmp_path):
    # Enable enforcement
    monkeypatch.setenv("JOBS_ENFORCE_LEASE_ACK", "true")
    db_path = tmp_path / "jobs.db"
    ensure_jobs_tables(db_path)
    jm = JobManager(db_path)

    j = jm.create_job(
        domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="1"
    )
    acq = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=10, worker_id="w1")
    assert acq is not None
    job_id = int(acq["id"])
    lease_id = str(acq.get("lease_id"))

    # Wrong worker/lease must fail
    ok_wrong = jm.complete_job(job_id, result={"ok": True}, worker_id="other", lease_id="bad")
    assert not ok_wrong
    # Still processing
    row = jm.get_job(job_id)
    assert row["status"] == "processing"

    # Correct worker/lease succeeds
    ok = jm.complete_job(job_id, result={"ok": True}, worker_id="w1", lease_id=lease_id)
    assert ok
    row2 = jm.get_job(job_id)
    assert row2["status"] == "completed"

