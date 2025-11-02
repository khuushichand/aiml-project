import os
from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.services.jobs_metrics_service import JobsMetricsService


def _set_env(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    # Point SQLite DB to test temp dir
    db_path = os.path.join(os.getcwd(), "Databases", "jobs.db")
    monkeypatch.setenv("JOBS_DB_PATH", db_path)
    # Use counters disabled here; service computes directly
    monkeypatch.delenv("JOBS_COUNTERS_ENABLED", raising=False)


def test_reconcile_group_cap(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    jm = JobManager()
    # Create two distinct groups
    j1 = jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="1")
    j2 = jm.create_job(domain="chatbooks", queue="default", job_type="import", payload={}, owner_user_id="1")
    svc = JobsMetricsService()
    # Reconcile only one group
    n = svc.reconcile_once(limit_groups=1)
    assert n == 1
    # Check job_counters: exactly one of the groups should be present
    conn = jm._connect()
    try:
        rows = conn.execute("SELECT domain, queue, job_type, ready_count FROM job_counters").fetchall() or []
        assert len(rows) == 1
        # Now reconcile the rest
        n2 = svc.reconcile_once(limit_groups=10)
        assert n2 >= 1
        rows2 = conn.execute("SELECT domain, queue, job_type FROM job_counters").fetchall() or []
        assert len(rows2) == 2
    finally:
        try:
            conn.close()
        except Exception:
            pass
