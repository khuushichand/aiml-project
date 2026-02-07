import os
import pytest

from tldw_Server_API.app.core.Jobs.manager import JobManager


@pytest.mark.unit
def test_integrity_sweep_clears_non_processing_lease(tmp_path, monkeypatch):
    db_path = tmp_path / "jobs.db"
    monkeypatch.setenv("JOBS_DB_PATH", str(db_path))
    jm = JobManager()
    j_queued = jm.create_job(domain="test", queue="default", job_type="t", payload={}, owner_user_id="u")
    j_processing = jm.create_job(domain="test", queue="default", job_type="t", payload={}, owner_user_id="u")
    # Manually inject two invalid states:
    # 1) queued job carrying lease metadata
    # 2) processing job with expired lease
    conn = jm._connect()
    try:
        conn.execute(
            "UPDATE jobs SET status='queued', lease_id='L', worker_id='W', leased_until=DATETIME('now') WHERE id = ?",
            (int(j_queued["id"]),),
        )
        conn.execute(
            "UPDATE jobs SET status='processing', leased_until=DATETIME('now','-10 minutes') WHERE id = ?",
            (int(j_processing["id"]),),
        )
        conn.commit()
    finally:
        conn.close()

    stats = jm.integrity_sweep(fix=True)
    assert stats["non_processing_with_lease"] == 1
    assert stats["processing_expired"] == 1
    assert stats["fixed"] == 2

    queued_after = jm.get_job(int(j_queued["id"]))
    processing_after = jm.get_job(int(j_processing["id"]))
    assert queued_after and not queued_after.get("lease_id") and not queued_after.get("worker_id")
    assert processing_after and processing_after.get("status") == "queued"
    assert not processing_after.get("lease_id") and not processing_after.get("worker_id")
