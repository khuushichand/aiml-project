import sqlite3
from datetime import datetime, timedelta

from tldw_Server_API.app.core.Jobs.migrations import ensure_jobs_tables
from tldw_Server_API.app.core.Jobs.manager import JobManager


def test_prune_jobs_by_status_and_age(tmp_path):
    db_path = tmp_path / "jobs.db"
    ensure_jobs_tables(db_path)
    jm = JobManager(db_path)

    # Create 3 jobs: 2 old completed/failed, 1 recent completed
    j1 = jm.create_job(domain="d", queue="default", job_type="t", payload={}, owner_user_id="1")
    j2 = jm.create_job(domain="d", queue="default", job_type="t", payload={}, owner_user_id="1")
    j3 = jm.create_job(domain="d", queue="default", job_type="t", payload={}, owner_user_id="1")

    # Acquire and complete/fail them to set terminal statuses
    acq = jm.acquire_next_job(domain="d", queue="default", lease_seconds=30, worker_id="w1")
    assert acq and int(acq["id"]) in {int(j1["id"]), int(j2["id"]), int(j3["id"])}
    jm.complete_job(int(acq["id"]))

    acq2 = jm.acquire_next_job(domain="d", queue="default", lease_seconds=30, worker_id="w1")
    assert acq2
    jm.fail_job(int(acq2["id"]), error="x", retryable=False)

    acq3 = jm.acquire_next_job(domain="d", queue="default", lease_seconds=30, worker_id="w1")
    assert acq3
    jm.complete_job(int(acq3["id"]))

    # Backdate j1/j2 completion times by 40 days
    conn = sqlite3.connect(db_path)
    try:
        old = (datetime.utcnow() - timedelta(days=40)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("UPDATE jobs SET completed_at=? WHERE id IN (?,?)", (old, int(j1["id"]), int(j2["id"])) )
        conn.commit()
    finally:
        conn.close()

    # Prune >30 days completed/failed
    deleted = jm.prune_jobs(statuses=["completed", "failed"], older_than_days=30)
    assert deleted >= 2
    # Remaining should include j3 (recent)
    r3 = jm.get_job(int(j3["id"]))
    assert r3 is not None
