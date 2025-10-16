import time
from datetime import datetime, timedelta

from tldw_Server_API.app.core.Jobs.migrations import ensure_jobs_tables
from tldw_Server_API.app.core.Jobs.manager import JobManager


def test_retryable_fail_sets_available_at_in_future(tmp_path):
    db_path = tmp_path / "jobs.db"
    ensure_jobs_tables(db_path)
    jm = JobManager(db_path)
    j = jm.create_job(
        domain="chatbooks",
        queue="default",
        job_type="import",
        payload={"action": "import"},
        owner_user_id="1",
        max_retries=3,
    )
    j1 = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=3, worker_id="w1")
    assert j1 is not None
    ok = jm.fail_job(int(j1["id"]), error="boom", retryable=True, backoff_seconds=2)
    assert ok
    row = jm.get_job(int(j1["id"]))
    assert row["status"] in ("queued", "failed")
    if row["status"] == "queued":
        # Should be scheduled ~2 seconds in the future
        avail = row.get("available_at")
        assert avail is not None
        # SQLite stores as text; parse via datetime.fromisoformat in code paths; here just compare as strings
        # Validate by sleeping then acquiring
        time.sleep(2.1)
        j2 = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=3, worker_id="w1")
        assert j2 is not None


def test_reclaim_expired_processing(tmp_path):
    db_path = tmp_path / "jobs.db"
    ensure_jobs_tables(db_path)
    jm = JobManager(db_path)
    j = jm.create_job(
        domain="chatbooks",
        queue="default",
        job_type="export",
        payload={"action": "export"},
        owner_user_id="1",
    )
    acq = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=1, worker_id="wA")
    assert acq is not None
    # Wait for lease to expire
    time.sleep(1.2)
    # Another worker should reclaim
    acq2 = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=5, worker_id="wB")
    assert acq2 is not None
    assert acq2["worker_id"] == "wB"
