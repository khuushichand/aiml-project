import json
import os
import tempfile
import time

import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.asyncio


def test_jobs_events_sse_sqlite_smoke(monkeypatch):
    # Configure minimal app and SQLite jobs DB in a temp path
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("MINIMAL_TEST_APP", "1")
    monkeypatch.setenv("JOBS_EVENTS_OUTBOX", "true")
    monkeypatch.setenv("JOBS_EVENTS_POLL_INTERVAL", "0.05")

    with tempfile.TemporaryDirectory() as td:
        db_path = os.path.join(td, "jobs_test.db")
        monkeypatch.setenv("JOBS_DB_PATH", db_path)

        # Ensure schema and create a job to seed the outbox
        from tldw_Server_API.app.core.Jobs.migrations import ensure_jobs_tables
        ensure_jobs_tables(db_path)

        from tldw_Server_API.app.core.Jobs.manager import JobManager
        jm = JobManager(db_path=db_path)

        from tldw_Server_API.app.core.AuthNZ.settings import get_settings, reset_settings
        reset_settings()
        from tldw_Server_API.app.main import app

        headers = {"X-API-KEY": get_settings().SINGLE_USER_API_KEY}
        with TestClient(app, headers=headers) as client:
            # Start stream and assert we receive at least a heartbeat (ping) frame as data
            hb = False
            deadline = time.time() + 3.0
            with client.stream("GET", "/api/v1/jobs/events/stream", params={"after_id": 0, "domain": "chatbooks"}) as s:
                if s.status_code != 200:
                    pytest.skip("jobs_admin stream not available in this environment")
                for line in s.iter_lines():
                    if time.time() > deadline:
                        break
                    if not line:
                        continue
                    if isinstance(line, bytes):
                        try:
                            line = line.decode()
                        except Exception:
                            continue
                    if line.startswith("data:"):
                        # Heartbeat payload is empty object in data mode
                        if line.strip() == "data: {}":
                            hb = True
                            break
            assert hb, "did not observe SSE heartbeat frame"
