import json
import os
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user


@pytest.mark.unit
def test_dlq_list_decrypt_and_redact(disable_heavy_startup, admin_user, redis_client, monkeypatch):
    # Ensure encryption key is set
    monkeypatch.setenv("EMBEDDINGS_DLQ_ENCRYPTION_KEY", "test-passphrase")
    from tldw_Server_API.app.core.Embeddings.dlq_crypto import encrypt_payload_if_configured

    # Create encrypted payload containing sensitive fields
    sensitive = {
        "api_key": "sk-THIS-IS-A-TEST-KEY",
        "authorization": "Bearer SECRET",
        "nested": {"token": "should-redact", "ok": "value"},
        "plain": "hello",
    }
    enc = encrypt_payload_if_configured(sensitive)
    assert enc is not None

    # Write a DLQ entry with payload_enc
    dlq_stream = "embeddings:embedding:dlq"
    _ = app  # app imported for context
    async def _write():
        await redis_client.xadd(dlq_stream, {
            "original_queue": "embeddings:embedding",
            "consumer_group": "embedding-group",
            "worker_id": "w1",
            "job_id": "job-enc",
            "job_type": "embedding",
            "error": "boom",
            "retry_count": "1",
            "max_retries": "1",
            "failed_at": "2025-01-01T00:00:00Z",
            "payload_enc": enc,
        })

    redis_client.run(_write())

    client = TestClient(app)
    r = client.get("/api/v1/embeddings/dlq", params={"stage": "embedding", "count": 10})
    assert r.status_code == 200
    data = r.json()
    # Find our job
    items = data.get("items", [])
    found = None
    for it in items:
        if it.get("job_id") == "job-enc":
            found = it
            break
    assert found is not None, "DLQ item not found"
    payload = found.get("payload")
    assert isinstance(payload, dict)
    # Sensitive keys should be redacted
    assert payload.get("api_key") == "***REDACTED***"
    assert payload.get("authorization") == "***REDACTED***"
    assert isinstance(payload.get("nested"), dict)
    assert payload["nested"].get("token") == "***REDACTED***"
    # Non-sensitive fields preserved
    assert payload.get("plain") == "hello"


class _StubAuditService:
    def __init__(self):
        self.events = []

    async def log_event(self, **kwargs):
        self.events.append(kwargs)
        return 1

    async def flush(self):
        return True


@pytest.mark.unit
def test_dlq_requeue_audited(disable_heavy_startup, admin_user, redis_client, monkeypatch):
    # Make sure audit service calls are captured
    stub = _StubAuditService()
    import tldw_Server_API.app.api.v1.endpoints.embeddings_v5_production_enhanced as emb_mod

    async def _get_audit_service_for_user(current_user=None):
        return stub

    monkeypatch.setattr(emb_mod, "get_audit_service_for_user", _get_audit_service_for_user)

    # Seed one DLQ entry
    async def _seed():
        await redis_client.xadd("embeddings:embedding:dlq", {
            "original_queue": "embeddings:embedding",
            "job_id": "job-audit",
            "error": "boom",
            "retry_count": "3",
            "max_retries": "3",
            "failed_at": "2025-01-01T00:00:00Z",
            "payload": json.dumps({"job_id": "job-audit"}),
        })

    redis_client.run(_seed())

    client = TestClient(app)
    # Requeue single
    resp = client.get("/api/v1/embeddings/dlq", params={"stage": "embedding", "count": 10})
    assert resp.status_code == 200
    entry_id = resp.json()["items"][0]["entry_id"]

    r2 = client.post("/api/v1/embeddings/dlq/requeue", json={"stage": "embedding", "entry_id": entry_id})
    assert r2.status_code == 200
    # Audit captured
    assert any(e.get("action") == "requeue" for e in stub.events)

    # Bulk requeue with a second item (not found + success mix)
    redis_client.run(_seed())
    resp2 = client.get("/api/v1/embeddings/dlq", params={"stage": "embedding", "count": 10})
    assert resp2.status_code == 200
    entry_ids = [it["entry_id"] for it in resp2.json()["items"]]
    r3 = client.post(
        "/api/v1/embeddings/dlq/requeue/bulk",
        json={"stage": "embedding", "entry_ids": entry_ids}
    )
    assert r3.status_code == 200
    assert any(e.get("action") == "bulk_requeue" for e in stub.events)
