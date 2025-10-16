import os
from datetime import datetime

from tldw_Server_API.app.core.Jobs.manager import JobManager


def test_adaptive_lease_fallback_sqlite(monkeypatch, tmp_path):
    # Enable adaptive lease; with no history, fallback should be max(min_s, 30) => default 30s
    monkeypatch.setenv("JOBS_ADAPTIVE_LEASE_ENABLE", "true")
    # Ensure min is default (15) and cap large enough
    monkeypatch.setenv("JOBS_ADAPTIVE_LEASE_MIN_SECONDS", "15")
    monkeypatch.setenv("JOBS_LEASE_MAX_SECONDS", "3600")
    # Permit test job_type and queue policy explicitly (defensive)
    monkeypatch.setenv("JOBS_ALLOWED_JOB_TYPES", "sample")
    monkeypatch.setenv("JOBS_ALLOWED_JOB_TYPES_CHATBOOKS", "sample")
    monkeypatch.setenv("JOBS_ALLOWED_QUEUES", "default,high,low")

    # Isolate DB to avoid state bleed
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("JOBS_DB_PATH", os.path.join(os.getcwd(), "Databases", "jobs.db"))
    jm = JobManager()

    j = jm.create_job(
        domain="chatbooks",
        queue="default",
        job_type="sample",
        payload={},
        owner_user_id="demo",
    )

    # Acquire with lease_seconds=0 to trigger adaptive path
    before = datetime.utcnow()
    got = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=0, worker_id="T1")
    assert got is not None

    # leased_until is stored as SQLite datetime string; parse with fromisoformat tolerant helper
    leased_until = got.get("leased_until")
    assert leased_until is not None
    # Accept either ISO or 'YYYY-MM-DD HH:MM:SS'
    ts = None
    try:
        ts = datetime.fromisoformat(str(leased_until).replace("Z", "+00:00"))
    except Exception:
        try:
            from datetime import datetime as _dt
            ts = _dt.strptime(str(leased_until), "%Y-%m-%d %H:%M:%S")
        except Exception:
            ts = None
    assert ts is not None
    delta = (ts - before).total_seconds()

    # Fallback target ~30s; allow tolerance for test timing
    assert 20 <= delta <= 45
