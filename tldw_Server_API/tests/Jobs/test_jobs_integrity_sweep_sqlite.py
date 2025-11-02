import os
import pytest

from tldw_Server_API.app.core.Jobs.manager import JobManager


@pytest.mark.unit
def test_integrity_sweep_clears_non_processing_lease(tmp_path, monkeypatch):
    db_path = tmp_path / "jobs.db"
    monkeypatch.setenv("JOBS_DB_PATH", str(db_path))
    jm = JobManager()
    j = jm.create_job(domain="test", queue="default", job_type="t", payload={}, owner_user_id="u")
    # Manually inject bad lease fields on a queued job
    conn = jm._connect()
    try:
        conn.execute("UPDATE jobs SET lease_id='L', worker_id='W', leased_until=DATETIME('now') WHERE id = ?", (int(j["id"]),))
        conn.commit()
    finally:
        conn.close()
    stats = jm.integrity_sweep(fix=True)
    assert stats["fixed"] >= 1
    j2 = jm.get_job(int(j["id"]))
    assert j2 and not j2.get("lease_id") and not j2.get("worker_id")
