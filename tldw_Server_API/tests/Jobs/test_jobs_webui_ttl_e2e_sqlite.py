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


def _backdate_runtime(job_id: int, seconds: int):
    jm = JobManager()
    conn = jm._connect()
    try:
        with conn:
            past = (datetime.utcnow() - timedelta(seconds=seconds)).strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                "UPDATE jobs SET started_at = ?, acquired_at = ? WHERE id = ?",
                (past, past, int(job_id)),
            )
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _get_group(stats, domain, queue, job_type):
    for row in stats:
        if row["domain"] == domain and row["queue"] == queue and row["job_type"] == job_type:
            return row
    return None


def test_webui_ttl_e2e_sqlite(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _set_env(monkeypatch)

    from tldw_Server_API.app.core.AuthNZ.settings import get_settings, reset_settings
    reset_settings()
    from tldw_Server_API.app.main import app

    jm = JobManager()
    # Seed a processing job
    j = jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="1")
    acq = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=60, worker_id="w1")
    assert acq is not None

    headers = {"X-API-KEY": get_settings().SINGLE_USER_API_KEY}
    with TestClient(app, headers=headers) as client:
        # Fetch stats before TTL
        r0 = client.get("/api/v1/jobs/stats", params={"domain": "chatbooks", "queue": "default", "job_type": "export"})
        assert r0.status_code == 200
        before = r0.json()
        grp_before = _get_group(before, "chatbooks", "default", "export")
        assert grp_before is not None
        assert grp_before["processing"] >= 1

        # Backdate runtime and run TTL sweep to cancel
        _backdate_runtime(int(acq["id"]), seconds=7200)
        r1 = client.post(
            "/api/v1/jobs/ttl/sweep",
            json={
                "runtime_seconds": 3600,
                "action": "cancel",
                "domain": "chatbooks",
                "queue": "default",
                "job_type": "export",
            },
            headers={**headers, "X-Confirm": "true"}
        )
        assert r1.status_code == 200
        assert r1.json()["affected"] >= 1

        # Fetch stats after TTL
        r2 = client.get("/api/v1/jobs/stats", params={"domain": "chatbooks", "queue": "default", "job_type": "export"})
        assert r2.status_code == 200
        after = r2.json()
        grp_after = _get_group(after, "chatbooks", "default", "export")
        assert grp_after is not None
        # processing should drop to 0 after cancellation
        assert grp_after["processing"] == 0
