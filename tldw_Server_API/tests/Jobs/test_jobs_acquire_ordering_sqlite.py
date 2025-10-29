import os
import pytest

from tldw_Server_API.app.core.Jobs.manager import JobManager


@pytest.mark.unit
def test_acquire_ordering_priority_desc(tmp_path, monkeypatch):
    db_path = tmp_path / "jobs.db"
    monkeypatch.setenv("JOBS_DB_PATH", str(db_path))
    jm = JobManager()
    j1 = jm.create_job(domain="test", queue="default", job_type="t", payload={}, owner_user_id="u", priority=1)
    j2 = jm.create_job(domain="test", queue="default", job_type="t", payload={}, owner_user_id="u", priority=5)
    j3 = jm.create_job(domain="test", queue="default", job_type="t", payload={}, owner_user_id="u", priority=10)
    acq1 = jm.acquire_next_job(domain="test", queue="default", lease_seconds=5, worker_id="w")
    assert acq1 and acq1.get("id") == j1["id"]  # priority 1 first
    # Complete to release for next acquire
    jm.complete_job(int(acq1["id"]), worker_id="w", lease_id=str(acq1.get("lease_id")), completion_token=str(acq1.get("lease_id")))
    acq2 = jm.acquire_next_job(domain="test", queue="default", lease_seconds=5, worker_id="w")
    assert acq2 and acq2.get("id") == j2["id"]  # then priority 5
    # Release next
    jm.complete_job(int(acq2["id"]), worker_id="w", lease_id=str(acq2.get("lease_id")), completion_token=str(acq2.get("lease_id")))
    acq3 = jm.acquire_next_job(domain="test", queue="default", lease_seconds=5, worker_id="w")
    assert acq3 and acq3.get("id") == j3["id"]  # finally priority 10
