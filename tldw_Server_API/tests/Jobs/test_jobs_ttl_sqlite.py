import os
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from tldw_Server_API.app.core.Jobs.manager import JobManager


def _set_env(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("SINGLE_USER_API_KEY", "sk-test")


def _backdate_sqlite_fields(job_id: int, *, created_delta_s: int = 0, runtime_delta_s: int = 0):
    jm = JobManager()
    conn = jm._connect()
    try:
        with conn:
            if created_delta_s:
                created_at = (datetime.utcnow() - timedelta(seconds=created_delta_s)).strftime("%Y-%m-%d %H:%M:%S")
                conn.execute(
                    "UPDATE jobs SET created_at = ?, updated_at = ? WHERE id = ?",
                    (created_at, created_at, int(job_id)),
                )
            if runtime_delta_s:
                started_at = (datetime.utcnow() - timedelta(seconds=runtime_delta_s)).strftime("%Y-%m-%d %H:%M:%S")
                conn.execute(
                    "UPDATE jobs SET started_at = ?, acquired_at = ? WHERE id = ?",
                    (started_at, started_at, int(job_id)),
                )
    finally:
        try:
            conn.close()
        except Exception:
            pass


def test_ttl_sweep_cancel(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _set_env(monkeypatch)

    from tldw_Server_API.app.main import app

    jm = JobManager()

    # Seed queued (age TTL) and processing (runtime TTL)
    j1 = jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="1")
    _backdate_sqlite_fields(int(j1["id"]), created_delta_s=3_600 * 2)  # created 2h ago

    j2 = jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="1")
    acq = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=30, worker_id="w1")
    assert acq is not None
    _backdate_sqlite_fields(int(acq["id"]), runtime_delta_s=3_600 * 3)  # running 3h

    headers = {"X-API-KEY": os.environ["SINGLE_USER_API_KEY"]}
    with TestClient(app, headers=headers) as client:
        body = {
            "age_seconds": 3600,  # 1h
            "runtime_seconds": 7200,  # 2h
            "action": "cancel",
            "domain": "chatbooks",
            "queue": "default",
            "job_type": "export",
        }
        r = client.post("/api/v1/jobs/ttl/sweep", json=body)
        assert r.status_code == 200, r.text
        affected = r.json()["affected"]
        assert affected >= 2

    # Verify statuses
    j1r = jm.get_job(int(j1["id"]))
    j2r = jm.get_job(int(acq["id"]))
    assert j1r and j1r["status"] == "cancelled"
    assert j2r and j2r["status"] == "cancelled"


def test_ttl_sweep_fail(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _set_env(monkeypatch)

    from tldw_Server_API.app.main import app

    jm = JobManager()
    j1 = jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="1")
    _backdate_sqlite_fields(int(j1["id"]), created_delta_s=3_600 * 2)

    acq = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=30, worker_id="w2")
    assert acq is not None
    _backdate_sqlite_fields(int(acq["id"]), runtime_delta_s=3_600 * 3)

    headers = {"X-API-KEY": os.environ["SINGLE_USER_API_KEY"]}
    with TestClient(app, headers=headers) as client:
        body = {
            "age_seconds": 3600,
            "runtime_seconds": 3600,
            "action": "fail",
            "domain": "chatbooks",
            "queue": "default",
            "job_type": "export",
        }
        r = client.post("/api/v1/jobs/ttl/sweep", json=body)
        assert r.status_code == 200
        assert r.json()["affected"] >= 2

    j1r = jm.get_job(int(j1["id"]))
    j2r = jm.get_job(int(acq["id"]))
    assert j1r and j1r["status"] == "failed"
    assert j2r and j2r["status"] == "failed"

