import os
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.Jobs.manager import JobManager


def _set_env(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.delenv("SINGLE_USER_API_KEY", raising=False)
    monkeypatch.setenv("JOBS_DB_PATH", os.path.join(os.getcwd(), "Databases", "jobs.db"))


def test_prune_ttl_batch_require_confirm_header(monkeypatch, tmp_path):
    _set_env(monkeypatch, tmp_path)
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings, reset_settings
    reset_settings()
    from tldw_Server_API.app.main import app

    jm = JobManager()
    # Seed a small set
    j = jm.create_job(domain="d", queue="default", job_type="t", payload={}, owner_user_id="1")
    jm.complete_job(int(j["id"]))

    headers = {"X-API-KEY": get_settings().SINGLE_USER_API_KEY}
    with TestClient(app, headers=headers) as client:
        # Prune without X-Confirm (dry_run false) -> 400
        body = {"statuses": ["completed"], "older_than_days": 0, "domain": "d", "queue": "default", "job_type": "t", "dry_run": False}
        r = client.post("/api/v1/jobs/prune", json=body)
        assert r.status_code == 400

        # TTL without X-Confirm -> 400
        r2 = client.post("/api/v1/jobs/ttl/sweep", json={"age_seconds": 0, "action": "cancel", "domain": "d"})
        assert r2.status_code == 400

        # Batch cancel without X-Confirm -> 400
        r3 = client.post("/api/v1/jobs/batch/cancel", json={"domain": "d"})
        assert r3.status_code == 400

        # Batch reschedule without X-Confirm -> 400
        r4 = client.post("/api/v1/jobs/batch/reschedule", json={"domain": "d", "delay_seconds": 10})
        assert r4.status_code == 400
