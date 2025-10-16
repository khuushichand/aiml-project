import os
import json
import time
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.Jobs.manager import JobManager


pytestmark = pytest.mark.pg_jobs


def _pg_env(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "true")
    dsn = os.getenv("JOBS_DB_URL")
    if not dsn:
        pytest.skip("JOBS_DB_URL not set for Postgres tests")
    monkeypatch.setenv("JOBS_EVENTS_OUTBOX", "true")
    monkeypatch.setenv("JOBS_EVENTS_POLL_INTERVAL", "0.05")


@pytest.mark.integration
def test_outbox_list_and_sse_postgres(monkeypatch):
    _pg_env(monkeypatch)
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings, reset_settings
    reset_settings()
    from tldw_Server_API.app.main import app

    jm = JobManager(backend="postgres", db_url=os.getenv("JOBS_DB_URL"))
    j = jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="u1")
    acq = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=5, worker_id="w1")
    assert acq is not None
    jm.fail_job(int(acq["id"]), error="boom", retryable=True, backoff_seconds=0)

    headers = {"X-API-KEY": get_settings().SINGLE_USER_API_KEY}
    with TestClient(app, headers=headers) as client:
        r = client.get("/api/v1/jobs/events", params={"after_id": 0, "domain": "chatbooks"})
        assert r.status_code == 200
        rows = r.json()
        assert any(ev["event_type"].startswith("job.") for ev in rows)

        with client.stream("GET", "/api/v1/jobs/events/stream", params={"after_id": 0}) as s:
            jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="u2")
            deadline = time.time() + 3.0
            ok = False
            for line in s.iter_lines():
                if not line:
                    if time.time() > deadline:
                        break
                    continue
                if isinstance(line, bytes):
                    line = line.decode()
                if line.startswith("data:"):
                    try:
                        obj = json.loads(line[len("data:"):].strip())
                        if obj.get("event") == "job.created":
                            ok = True
                            break
                    except Exception:
                        pass
                if time.time() > deadline:
                    break
            assert ok
