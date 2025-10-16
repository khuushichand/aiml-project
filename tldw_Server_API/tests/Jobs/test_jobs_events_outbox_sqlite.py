import os
import json
import pytest
import time
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.Jobs.manager import JobManager


def _setup_env(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("JOBS_EVENTS_OUTBOX", "true")
    monkeypatch.setenv("JOBS_EVENTS_POLL_INTERVAL", "0.05")
    monkeypatch.setenv("JOBS_DB_PATH", os.path.join(os.getcwd(), "Databases", "jobs.db"))


@pytest.mark.integration
def test_outbox_list_and_sse_sqlite(monkeypatch, tmp_path):
    _setup_env(monkeypatch, tmp_path)

    # Import app after env
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings, reset_settings
    reset_settings()
    from tldw_Server_API.app.main import app

    jm = JobManager()

    # Seed a few events by exercising core paths (and force an outbox write)
    j = jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="u1")
    acq = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=5, worker_id="w1")
    assert acq is not None
    jm.fail_job(int(acq["id"]), error="boom", retryable=True, backoff_seconds=0)
    # Force-write a synthetic event to outbox to validate list/stream independently of manager wiring
    from tldw_Server_API.app.core.Jobs.event_stream import emit_job_event
    emit_job_event("jobs.test_event", job={"id": int(j["id"]), "domain": "chatbooks", "queue": "default", "job_type": "export"}, attrs={"x": 1})

    headers = {"X-API-KEY": get_settings().SINGLE_USER_API_KEY}
    with TestClient(app, headers=headers) as client:
        # List outbox
        time.sleep(0.05)
        r = client.get("/api/v1/jobs/events", params={"after_id": 0})
        assert r.status_code == 200, r.text
        rows = r.json()
        # Expect at least the synthetic event we pushed
        assert any(ev["event_type"] == "jobs.test_event" for ev in rows)

        # SSE stream: open stream, create a new event, and ensure we receive it
        with client.stream("GET", "/api/v1/jobs/events/stream", params={"after_id": 0}) as s:
            # Create an event after the stream starts (synthetic to outbox)
            emit_job_event("jobs.test_event_2", job={"id": int(j["id"]), "domain": "chatbooks", "queue": "default", "job_type": "export"}, attrs={"y": 1})
            deadline = time.time() + 3.0
            got = False
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
                        if obj.get("event") == "jobs.test_event_2":
                            got = True
                            break
                    except Exception:
                        pass
                if time.time() > deadline:
                    break
            assert got, "Did not receive job.created event from SSE stream"
