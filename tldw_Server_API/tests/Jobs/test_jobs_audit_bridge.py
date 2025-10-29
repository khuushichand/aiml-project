import sqlite3
import time
import pytest

from tldw_Server_API.app.core.Jobs.migrations import ensure_jobs_tables


def test_audit_bridge_logs_job_create(monkeypatch, tmp_path):
    # Skip gracefully if unified audit is unavailable (optional dependency)
    try:
        from tldw_Server_API.app.core.Audit.unified_audit_service import UnifiedAuditService  # noqa: F401
    except Exception:
        pytest.skip("Unified audit service unavailable; skipping audit bridge test")
    audit_db = tmp_path / "jobs_audit.db"
    monkeypatch.setenv("JOBS_AUDIT_ENABLED", "1")
    monkeypatch.setenv("JOBS_AUDIT_DB_PATH", str(audit_db))

    from tldw_Server_API.app.core.Jobs.audit_bridge import shutdown_jobs_audit_bridge
    from tldw_Server_API.app.core.Jobs.manager import JobManager

    jobs_db = tmp_path / "jobs.db"
    ensure_jobs_tables(jobs_db)
    jm = JobManager(jobs_db)

    jm.create_job(
        domain="audit-test",
        queue="default",
        job_type="example",
        payload={"foo": "bar"},
        owner_user_id="u-1",
    )

    # Give the background audit worker a moment to persist the event.
    timeout = time.time() + 5.0
    while time.time() < timeout:
        if audit_db.exists():
            with sqlite3.connect(audit_db) as conn:
                row = conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()
                if row and row[0] >= 1:
                    shutdown_jobs_audit_bridge()
                    return
        time.sleep(0.05)

    shutdown_jobs_audit_bridge()
    raise AssertionError("Expected at least one audit event for job creation")
