import os
import time
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.Jobs.manager import JobManager


def _init_env(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.delenv("SINGLE_USER_API_KEY", raising=False)
    monkeypatch.setenv("JOBS_DB_PATH", os.path.join(os.getcwd(), "Databases", "jobs.db"))
    monkeypatch.setenv("JOBS_QUARANTINE_THRESHOLD", "1")


@pytest.mark.unit
def test_endpoint_requeue_quarantined_sqlite(monkeypatch, tmp_path):
    _init_env(monkeypatch, tmp_path)
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings, reset_settings
    reset_settings()
    from tldw_Server_API.app.main import app

    jm = JobManager()
    # Create job and move to quarantined in one retry (threshold=1)
    j = jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="1")
    acq = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=5, worker_id="w")
    assert acq and acq.get("id") == j["id"]
    jm.fail_job(int(j["id"]), error="boom", retryable=True, backoff_seconds=0, worker_id="w", lease_id=str(acq.get("lease_id")), error_code="E1")
    row = jm.get_job(int(j["id"]))
    assert row and row.get("status") == "quarantined"

    headers = {"X-API-KEY": get_settings().SINGLE_USER_API_KEY}
    with TestClient(app, headers=headers) as client:
        # Dry run should report count but keep status
        r = client.post("/api/v1/jobs/batch/requeue_quarantined", json={"domain": "chatbooks", "queue": "default", "job_type": "export", "dry_run": True})
        assert r.status_code == 200
        assert r.json()["affected"] >= 1
        row2 = jm.get_job(int(j["id"]))
        assert row2 and row2.get("status") == "quarantined"

        # Real run requires confirm header
        r2 = client.post(
            "/api/v1/jobs/batch/requeue_quarantined",
            headers={**headers, "X-Confirm": "true"},
            json={"domain": "chatbooks", "queue": "default", "job_type": "export", "dry_run": False},
        )
        assert r2.status_code == 200
        assert r2.json()["affected"] >= 1
        row3 = jm.get_job(int(j["id"]))
        assert row3 and row3.get("status") == "queued"
        assert (row3.get("failure_streak_count") or 0) == 0

