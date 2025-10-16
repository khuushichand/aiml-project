import time

from tldw_Server_API.app.core.Jobs.migrations import ensure_jobs_tables
from tldw_Server_API.app.core.Jobs.manager import JobManager


def test_priority_fairness_in_acquire(tmp_path):
    db_path = tmp_path / "jobs.db"
    ensure_jobs_tables(db_path)
    jm = JobManager(db_path)
    # Two jobs, different priorities
    j_low = jm.create_job(
        domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="1", priority=1
    )
    j_high = jm.create_job(
        domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="1", priority=9
    )
    first = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=5, worker_id="w1")
    assert first is not None
    # Higher numeric priority should be acquired first (DESC)
    assert int(first["id"]) == int(j_high["id"])  # priority 9 before 1


def test_renew_prevents_reclaim(tmp_path):
    db_path = tmp_path / "jobs.db"
    ensure_jobs_tables(db_path)
    jm = JobManager(db_path)
    j = jm.create_job(
        domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="1"
    )
    acq = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=1, worker_id="wA")
    assert acq is not None
    # Renew before expiry
    # Provide worker_id/lease_id to exercise enforced path as well
    ok = jm.renew_job_lease(int(acq["id"]), seconds=2, worker_id=str(acq.get("worker_id") or "wA"), lease_id=str(acq.get("lease_id")))
    assert ok
    # Wait 1.2s; should still be leased
    time.sleep(1.2)
    acq2 = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=5, worker_id="wB")
    assert acq2 is None
    # Wait remaining time to expire
    time.sleep(1.0)
    acq3 = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=5, worker_id="wB")
    assert (acq3 is None) or (int(acq3["id"]) == int(j["id"]))
