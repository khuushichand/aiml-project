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
    # Lower number means higher priority (ASC): 1 before 9
    assert int(first["id"]) == int(j_low["id"])  # priority 1 before 9


def test_renew_prevents_reclaim(monkeypatch, tmp_path):
    # Ensure renew can extend beyond 1s even if a global cap is present
    monkeypatch.delenv("JOBS_LEASE_MAX_SECONDS", raising=False)
    monkeypatch.setenv("JOBS_LEASE_MAX_SECONDS", "10")
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
    ok = jm.renew_job_lease(int(acq["id"]), seconds=3, worker_id=str(acq.get("worker_id") or "wA"), lease_id=str(acq.get("lease_id")))
    assert ok
    # Wait well under renewed lease; should still be leased
    time.sleep(1.5)
    acq2 = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=5, worker_id="wB")
    assert acq2 is None
    # Wait remaining time to expire
    time.sleep(2.0)
    acq3 = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=5, worker_id="wB")
    assert (acq3 is None) or (int(acq3["id"]) == int(j["id"]))
