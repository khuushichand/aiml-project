import os
import json
import time
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.tests.helpers.pg import pg_dsn


pytestmark = pytest.mark.pg_jobs


def _pg_env(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "true")
    # Minimize app startup and disable unrelated background workers
    monkeypatch.setenv("MINIMAL_TEST_APP", "1")
    monkeypatch.setenv("CHATBOOKS_CORE_WORKER_ENABLED", "false")
    monkeypatch.setenv("JOBS_METRICS_GAUGES_ENABLED", "false")
    monkeypatch.setenv("JOBS_METRICS_RECONCILE_ENABLE", "false")
    monkeypatch.setenv("AUDIO_JOBS_WORKER_ENABLED", "false")
    monkeypatch.setenv("EMBEDDINGS_REEMBED_WORKER_ENABLED", "false")
    monkeypatch.setenv("JOBS_WEBHOOKS_ENABLED", "false")
    monkeypatch.setenv("WORKFLOWS_WEBHOOK_DLQ_ENABLED", "false")
    monkeypatch.setenv("WORKFLOWS_ARTIFACT_GC_ENABLED", "false")
    monkeypatch.setenv("WORKFLOWS_DB_MAINTENANCE_ENABLED", "false")
    monkeypatch.setenv("PRIVILEGE_METADATA_VALIDATE_ON_STARTUP", "0")
    # Prefer shared DSN helper, but honor existing env if explicitly set
    if pg_dsn:
        monkeypatch.setenv("JOBS_DB_URL", pg_dsn)
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

        # Create and complete a job and assert exactly one job.completed event
        j3 = jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="u3")
        acq3 = jm.acquire_next_job(domain="chatbooks", queue="default", lease_seconds=5, worker_id="w3")
        assert acq3 is not None
        jm.complete_job(int(acq3["id"]))

        # Poll list endpoint to find job.completed for this job
        deadline2 = time.time() + 3.0
        count = 0
        while time.time() < deadline2 and count == 0:
            r = client.get("/api/v1/jobs/events", params={"after_id": 0, "domain": "chatbooks"})
            assert r.status_code == 200
            rows = r.json()
            count = sum(1 for ev in rows if ev.get("event_type") == "job.completed" and int(ev.get("job_id") or 0) == int(j3["id"]))
            if count == 0:
                time.sleep(0.05)
        assert count == 1, f"expected 1 job.completed event for job {j3['id']}, found {count}"


@pytest.mark.integration
def test_outbox_after_id_and_filters_postgres(monkeypatch):
    monkeypatch.setenv("JOBS_EVENTS_OUTBOX", "true")
    monkeypatch.setenv("JOBS_EVENTS_POLL_INTERVAL", "0.05")
    if not pg_dsn:
        pytest.skip("JOBS_DB_URL not set for Postgres tests")
    monkeypatch.setenv("JOBS_DB_URL", pg_dsn)
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings, reset_settings
    reset_settings()
    from tldw_Server_API.app.core.Jobs.pg_migrations import ensure_jobs_tables_pg
    ensure_jobs_tables_pg(pg_dsn)
    jm = JobManager(backend="postgres", db_url=pg_dsn)
    j1 = jm.create_job(domain="chatbooks", queue="default", job_type="export", payload={}, owner_user_id="u1")
    j2 = jm.create_job(domain="other", queue="default", job_type="import", payload={}, owner_user_id="u2")

    from tldw_Server_API.app.core.Jobs.event_stream import emit_job_event
    emit_job_event("jobs.filter_test", job={"id": int(j1["id"]), "domain": "chatbooks", "queue": "default", "job_type": "export"}, attrs={})
    emit_job_event("jobs.filter_test", job={"id": int(j2["id"]), "domain": "other", "queue": "default", "job_type": "import"}, attrs={})

    from fastapi.testclient import TestClient
    from tldw_Server_API.app.main import app
    headers = {"X-API-KEY": get_settings().SINGLE_USER_API_KEY}
    with TestClient(app, headers=headers) as client:
        r = client.get("/api/v1/jobs/events", params={"after_id": 0, "domain": "chatbooks"})
        assert r.status_code == 200
        rows = r.json()
        assert all(ev.get("domain") == "chatbooks" for ev in rows)
        last_id = rows[-1]["id"] if rows else 0
        emit_job_event("jobs.paging_test", job={"id": int(j1["id"]), "domain": "chatbooks", "queue": "default", "job_type": "export"}, attrs={})
        r2 = client.get("/api/v1/jobs/events", params={"after_id": int(last_id)})
        assert r2.status_code == 200
        rows2 = r2.json()
        assert all(ev["id"] > int(last_id) for ev in rows2)
        with client.stream("GET", "/api/v1/jobs/events/stream", params={"after_id": 0}):
            pass
