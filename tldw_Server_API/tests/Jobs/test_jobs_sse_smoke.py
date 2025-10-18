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


@pytest.mark.integration
def test_jobs_events_sse_initial_data_within_500ms(monkeypatch, tmp_path):
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
        start = time.time()
        with client.stream("GET", "/api/v1/jobs/events/stream", params={"after_id": 0}) as s:
            got_first_data = False
            elapsed = None
            deadline = start + max_seconds
            for line in s.iter_lines():
                now = time.time()
                if line:
                    if isinstance(line, bytes):
                        line = line.decode()
                    # We expect a first data line from initial ping
                    if str(line).startswith("data:"):
                        got_first_data = True
                        elapsed = now - start
                        break
                if now > deadline:
                    break

        assert got_first_data, f"SSE did not deliver initial data within {max_seconds:.3f}s"
        # If we captured an elapsed time, enforce the budget explicitly
        assert elapsed is not None and elapsed <= max_seconds, (
            f"Initial SSE data arrived too late: {elapsed:.3f}s > {max_seconds:.3f}s"
        )

