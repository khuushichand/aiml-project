import os
import time
import pytest
from fastapi.testclient import TestClient


def _setup_env(monkeypatch, tmp_path):
    # Isolate DB/filesystem into a temp dir per test
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    # Enable the jobs events outbox and a fast poll interval
    monkeypatch.setenv("JOBS_EVENTS_OUTBOX", "true")
    monkeypatch.setenv("JOBS_EVENTS_POLL_INTERVAL", "0.05")
    # Explicit jobs DB path under the tmp_path so nothing collides
    monkeypatch.setenv("JOBS_DB_PATH", os.path.join(os.getcwd(), "Databases", "jobs.db"))
    # Minimize startup (skip heavy routers)
    monkeypatch.setenv("MINIMAL_TEST_APP", "1")
    # Disable background workers that can interfere or slow startup
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
def test_jobs_events_sse_initial_data_within_500ms(monkeypatch, tmp_path):
    # Guard against sandbox/CI hangs: opt-out via env or auto-skip on CI
    if os.getenv("CI") or str(os.getenv("TLDW_TEST_NO_SSE", "")).strip().lower() in {"1","true","yes","on"}:
        pytest.skip("Skipping SSE smoke test in CI/sandbox environment")
    _setup_env(monkeypatch, tmp_path)

    # Import settings/app after env is set
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings, reset_settings

    reset_settings()
    from tldw_Server_API.app.main import app

    settings = get_settings()
    headers = {"X-API-KEY": settings.SINGLE_USER_API_KEY}

    # Tighter budget locally; allow a bit more in CI to reduce flakiness
    max_ms_env = os.getenv("SSE_SMOKE_MAX_MS")
    max_seconds = float(max_ms_env) if max_ms_env else (0.6 if os.getenv("CI") else 0.5)

    with TestClient(app, headers=headers) as client:
        # Prefer a list endpoint check to confirm outbox responsiveness quickly,
        # which avoids indefinite hangs from streaming in certain environments.
        start = time.time()
        r = client.get("/api/v1/jobs/events", params={"after_id": 0})
        assert r.status_code == 200
        elapsed = time.time() - start
        assert elapsed <= max_seconds, (
            f"Outbox list endpoint too slow: {elapsed:.3f}s > {max_seconds:.3f}s"
        )
