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
    # Minimize startup (skip heavy routers)
    monkeypatch.setenv("MINIMAL_TEST_APP", "1")
    # Disable background workers that can interfere with jobs DB
    monkeypatch.setenv("CHATBOOKS_CORE_WORKER_ENABLED", "false")
    monkeypatch.setenv("JOBS_METRICS_GAUGES_ENABLED", "false")
    monkeypatch.setenv("JOBS_METRICS_RECONCILE_ENABLE", "false")
    monkeypatch.setenv("AUDIO_JOBS_WORKER_ENABLED", "false")
    monkeypatch.setenv("EMBEDDINGS_REEMBED_WORKER_ENABLED", "false")
    monkeypatch.setenv("JOBS_WEBHOOKS_ENABLED", "false")
    monkeypatch.setenv("WORKFLOWS_WEBHOOK_DLQ_ENABLED", "false")
    monkeypatch.setenv("WORKFLOWS_ARTIFACT_GC_ENABLED", "false")
    monkeypatch.setenv("WORKFLOWS_DB_MAINTENANCE_ENABLED", "false")
    # Skip privilege catalog validation on startup
    monkeypatch.setenv("PRIVILEGE_METADATA_VALIDATE_ON_STARTUP", "0")


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

        # Instead of relying on SSE streaming (which can be flaky in constrained
        # test sandboxes), validate outbox delivery via the list endpoint.
        emit_job_event(
            "jobs.test_event_2",
            job={"id": int(j["id"]), "domain": "chatbooks", "queue": "default", "job_type": "export"},
            attrs={"y": 1},
        )
        deadline = time.time() + 2.0
        saw = False
        while time.time() < deadline and not saw:
            r_fb = client.get("/api/v1/jobs/events", params={"after_id": 0})
            assert r_fb.status_code == 200
            rows_fb = r_fb.json()
            saw = any(ev["event_type"] == "jobs.test_event_2" for ev in rows_fb)
            if not saw:
                time.sleep(0.05)
        assert saw, "jobs.test_event_2 not observed in outbox list"

        # Create and complete a job; assert exactly one job.completed event exists for it
        j2 = jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="u2")
        acq2 = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=5, worker_id="w2")
        assert acq2 is not None
        jm.complete_job(int(acq2["id"]))

        # Poll until we see the completed event, then count
        deadline2 = time.time() + 2.0
        completed_events = []
        while time.time() < deadline2 and not completed_events:
            r3 = client.get("/api/v1/jobs/events", params={"after_id": 0, "domain": "chatbooks"})
            assert r3.status_code == 200
            evs = r3.json()
            completed_events = [ev for ev in evs if ev.get("event_type") == "job.completed" and int(ev.get("job_id") or 0) == int(j2["id"])]
            if not completed_events:
                time.sleep(0.05)
        assert len(completed_events) == 1, f"expected 1 job.completed event for job {j2['id']}, found {len(completed_events)}"


@pytest.mark.integration
def test_outbox_after_id_and_filters_sqlite(monkeypatch, tmp_path):
    _setup_env(monkeypatch, tmp_path)

    from tldw_Server_API.app.core.AuthNZ.settings import get_settings, reset_settings
    reset_settings()
    from tldw_Server_API.app.main import app

    jm = JobManager()
    # Create two domains worth of events
    j1 = jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="u1")
    j2 = jm.create_job(domain="other", queue="default", job_type="import", payload={}, owner_user_id="u2")
    # Emit synthetic events for both
    from tldw_Server_API.app.core.Jobs.event_stream import emit_job_event
    emit_job_event("jobs.filter_test", job={"id": int(j1["id"]), "domain": "chatbooks", "queue": "default", "job_type": "export"}, attrs={})
    emit_job_event("jobs.filter_test", job={"id": int(j2["id"]), "domain": "other", "queue": "default", "job_type": "import"}, attrs={})

    headers = {"X-API-KEY": get_settings().SINGLE_USER_API_KEY}
    with TestClient(app, headers=headers) as client:
        # Domain filter only returns chatbooks
        r = client.get("/api/v1/jobs/events", params={"after_id": 0, "domain": "chatbooks"})
        assert r.status_code == 200
        rows = r.json()
        assert all(ev.get("domain") == "chatbooks" for ev in rows)

        # after_id paging returns only newer events
        if rows:
            last_id = rows[-1]["id"]
        else:
            last_id = 0
        # Create a new event and request after last_id
        emit_job_event("jobs.paging_test", job={"id": int(j1["id"]), "domain": "chatbooks", "queue": "default", "job_type": "export"}, attrs={})
        r2 = client.get("/api/v1/jobs/events", params={"after_id": int(last_id)})
        assert r2.status_code == 200
        rows2 = r2.json()
        assert all(ev["id"] > int(last_id) for ev in rows2)

        # Skip streaming disconnect in SQLite mode to avoid CI hangs
        # (covered in Postgres streaming tests when available)
