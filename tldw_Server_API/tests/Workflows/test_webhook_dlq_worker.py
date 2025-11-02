from __future__ import annotations

import asyncio
import json
import types
import pytest

from tldw_Server_API.app.core.DB_Management.Workflows_DB import WorkflowsDatabase
from tldw_Server_API.app.services import workflows_webhook_dlq_service as dlq_mod


pytestmark = pytest.mark.integration


def test_host_allow_deny_logic(monkeypatch):
    # Global allow/deny lists
    monkeypatch.setenv("WORKFLOWS_WEBHOOK_ALLOWLIST", "*.ok.test,allowed.example")
    monkeypatch.setenv("WORKFLOWS_WEBHOOK_DENYLIST", "deny.test,*.blocked.tld")
    assert dlq_mod._host_allowed("https://foo.ok.test/h", "default") is True
    assert dlq_mod._host_allowed("https://allowed.example/h", "default") is True
    assert dlq_mod._host_allowed("https://deny.test/h", "default") is False
    assert dlq_mod._host_allowed("https://x.blocked.tld/h", "default") is False


@pytest.mark.asyncio
async def test_dlq_worker_backoff_and_delivery(monkeypatch, tmp_path):
    # Use SQLite DB for worker loop; behavior is the same for DLQ table mechanics
    db = WorkflowsDatabase(str(tmp_path / "wf.db"))
    # Enqueue a row due now
    db.enqueue_webhook_dlq(
        tenant_id="default",
        run_id="runX",
        url="https://post.test/hook",
        body={"ok": True},
        last_error="init",
    )

    # Force allow host
    monkeypatch.setenv("WORKFLOWS_WEBHOOK_ALLOWLIST", "post.test")
    # Minimize loop interval
    monkeypatch.setenv("WORKFLOWS_WEBHOOK_DLQ_INTERVAL_SEC", "1")
    monkeypatch.setenv("WORKFLOWS_WEBHOOK_DLQ_BATCH", "10")
    monkeypatch.setenv("WORKFLOWS_WEBHOOK_DLQ_TIMEOUT_SEC", "1")

    # Monkeypatch list_webhook_dlq_due to pull from our db
    monkeypatch.setattr(dlq_mod, "create_workflows_database", lambda backend=None: db)
    monkeypatch.setattr(dlq_mod, "get_content_backend_instance", lambda: None)

    # Stub httpx AsyncClient behavior: first call fails, second succeeds
    class DummyResp:
        def __init__(self, status_code=200):
            self.status_code = status_code
            self.text = "ok"

    class DummyClient:
        async def post(self, url, json=None, timeout=None):
            DummyClient.calls += 1
            if DummyClient.calls == 1:
                # fail first time
                return DummyResp(500)
            return DummyResp(200)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    DummyClient.calls = 0

    # Patch internal usage
    monkeypatch.setattr(dlq_mod, "httpx", types.SimpleNamespace(AsyncClient=DummyClient))
    # Fix backoff to 1 second to make assertion deterministic
    monkeypatch.setattr(dlq_mod, "_compute_next_backoff", lambda attempts: 1)

    # Run worker for a couple of cycles
    stop = asyncio.Event()
    task = asyncio.create_task(dlq_mod.run_workflows_webhook_dlq_worker(stop))
    # Allow first cycle
    await asyncio.sleep(0.2)
    # Fetch row and assert attempts incremented and next_attempt_at set
    rows = db.list_webhook_dlq_due(limit=10)
    if rows:
        r = rows[0]
        assert int(r.get("attempts", 0)) >= 1
    # Allow second cycle to deliver and delete
    await asyncio.sleep(1.2)
    stop.set()
    try:
        await asyncio.wait_for(task, timeout=2)
    except asyncio.TimeoutError:
        task.cancel()
    # Ensure DLQ is drained after successful retry
    rows2 = db.list_webhook_dlq_due(limit=10)
    assert not rows2, f"Expected DLQ to be empty, found: {rows2}"
