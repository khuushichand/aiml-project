import os
import pytest

from tldw_Server_API.app.core.Jobs.manager import JobManager


@pytest.mark.unit
def test_completion_idempotent_sqlite(tmp_path, monkeypatch):
    db_path = tmp_path / "jobs.db"
    monkeypatch.setenv("JOBS_DB_PATH", str(db_path))
    jm = JobManager()
    j = jm.create_job(domain="test", queue="default", job_type="t", payload={}, owner_user_id="u")
    acq = jm.acquire_next_job(domain="test", queue="default", lease_seconds=10, worker_id="w1")
    assert acq and acq.get("id") == j["id"]
    token = str(acq.get("lease_id"))
    ok1 = jm.complete_job(int(j["id"]), worker_id="w1", lease_id=token, completion_token=token)
    assert ok1 is True
    # Repeat with same token (idempotent)
    ok2 = jm.complete_job(int(j["id"]), worker_id="w1", lease_id=token, completion_token=token)
    assert ok2 is True
    # Different token should not re-finalize
    ok3 = jm.complete_job(int(j["id"]), worker_id="w1", lease_id=token, completion_token="other-token")
    assert ok3 is False
