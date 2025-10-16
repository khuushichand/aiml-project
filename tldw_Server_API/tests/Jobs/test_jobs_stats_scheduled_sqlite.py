import os
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from tldw_Server_API.app.core.Jobs.manager import JobManager


def _set_env(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.delenv("SINGLE_USER_API_KEY", raising=False)
    import os as _os
    monkeypatch.setenv("JOBS_DB_PATH", _os.path.join(_os.getcwd(), "Databases", "jobs.db"))


def test_jobs_stats_includes_scheduled_sqlite(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _set_env(monkeypatch)

    from tldw_Server_API.app.core.AuthNZ.settings import get_settings, reset_settings
    reset_settings()
    from tldw_Server_API.app.main import app

    jm = JobManager()
    # Create a scheduled job (available in the future)
    future = datetime.utcnow() + timedelta(hours=1)
    jm.create_job(
        domain="chatbooks",
        queue="default",
        job_type="export",
        payload={},
        owner_user_id="1",
        available_at=future,
    )

    headers = {"X-API-KEY": get_settings().SINGLE_USER_API_KEY}
    with TestClient(app, headers=headers) as client:
        r = client.get("/api/v1/jobs/stats", params={"domain": "chatbooks", "queue": "default", "job_type": "export"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body) == 1
        row = body[0]
        assert row["queued"] == 0  # ready queued
        assert row["scheduled"] >= 1
        assert row["processing"] == 0
