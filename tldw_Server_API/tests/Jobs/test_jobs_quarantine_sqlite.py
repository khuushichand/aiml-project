import os
import time
import pytest

from tldw_Server_API.app.core.Jobs.manager import JobManager


@pytest.mark.unit
def test_poison_quarantine_on_retries(tmp_path, monkeypatch):
    db_path = tmp_path / "jobs.db"
    monkeypatch.setenv("JOBS_DB_PATH", str(db_path))
    monkeypatch.setenv("JOBS_QUARANTINE_THRESHOLD", "2")
    jm = JobManager()
    j = jm.create_job(domain="test", queue="default", job_type="t", payload={}, owner_user_id="u")
    acq = jm.acquire_next_job(domain="test", queue="default", lease_seconds=5, worker_id="w")
    assert acq and acq.get("id") == j["id"]
    lease_id = str(acq.get("lease_id"))
    # First retryable failure with code E1 -> requeued
    ok1 = jm.fail_job(int(j["id"]), error="boom", retryable=True, backoff_seconds=0, worker_id="w", lease_id=lease_id, error_code="E1")
    assert ok1 is True
    # Reacquire
    time.sleep(1.1)
    acq2 = jm.acquire_next_job(domain="test", queue="default", lease_seconds=5, worker_id="w")
    assert acq2 and acq2.get("id") == j["id"]
    # Second same-code failure -> hits threshold and quarantines
    ok2 = jm.fail_job(int(j["id"]), error="boom", retryable=True, worker_id="w", lease_id=str(acq2.get("lease_id")), error_code="E1")
    assert ok2 is True
    row = jm.get_job(int(j["id"]))
    assert row and row.get("status") == "quarantined"
