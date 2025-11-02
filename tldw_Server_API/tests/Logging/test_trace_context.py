import types
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.Logging.log_context import ensure_traceparent


def test_ensure_traceparent_sets_state_and_returns_value():
    class _State:  # minimal stand-in for request.state
        pass

    class _Req:
        def __init__(self, headers: Dict[str, str]):
            self.headers = headers
            self.state = _State()

    tp = "00-0123456789abcdef0123456789abcdef-0123456789abcdef-01"
    req = _Req({"traceparent": tp})
    out = ensure_traceparent(req)
    assert out == tp
    assert getattr(req.state, "traceparent") == tp

    # Case-insensitive header
    req2 = _Req({"Traceparent": tp})
    out2 = ensure_traceparent(req2)
    assert out2 == tp
    assert getattr(req2.state, "traceparent") == tp


def test_audio_jobs_submit_propagates_request_id(monkeypatch):
    # Capture kwargs sent to JobManager.create_job
    captured: Dict[str, Any] = {}

    from tldw_Server_API.app.core.Jobs import manager as jobs_manager

    def fake_create_job(self, *, domain, queue, job_type, payload, owner_user_id, project_id=None,
                        priority=5, max_retries=3, available_at=None, idempotency_key=None,
                        request_id=None, trace_id=None):  # signature-compatible
        captured.update({
            "domain": domain,
            "queue": queue,
            "job_type": job_type,
            "payload": payload,
            "owner_user_id": owner_user_id,
            "request_id": request_id,
        })
        return {"id": 42, "uuid": "u", "domain": domain, "queue": queue, "job_type": job_type, "status": "queued"}

    monkeypatch.setattr(jobs_manager.JobManager, "create_job", fake_create_job, raising=True)

    client = TestClient(app)
    resp = client.post(
        "/api/v1/audio/jobs/submit",
        json={"url": "https://example.com/a.mp3"},
        headers={
            "X-API-KEY": "test-api-key-12345",
            "X-Request-ID": "req-123",
            "traceparent": "00-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-bbbbbbbbbbbbbbbb-01",
        },
    )
    assert resp.status_code == 200, resp.text
    assert captured.get("request_id") == "req-123"


def test_reembed_schedule_propagates_request_id(monkeypatch):
    captured: Dict[str, Any] = {}

    from tldw_Server_API.app.core.Jobs import manager as jobs_manager

    def fake_create_job(self, *, domain, queue, job_type, payload, owner_user_id, project_id=None,
                        priority=5, max_retries=3, available_at=None, idempotency_key=None,
                        request_id=None, trace_id=None):
        captured.update({
            "domain": domain,
            "queue": queue,
            "job_type": job_type,
            "payload": payload,
            "owner_user_id": owner_user_id,
            "request_id": request_id,
        })
        return {"id": 99, "uuid": "u2", "domain": domain, "queue": queue, "job_type": job_type, "status": "queued"}

    monkeypatch.setattr(jobs_manager.JobManager, "create_job", fake_create_job, raising=True)

    client = TestClient(app)
    resp = client.post(
        "/api/v1/embeddings/reembed/schedule",
        json={"media_id": 1},
        headers={
            "X-API-KEY": "test-api-key-12345",
            "X-Request-ID": "req-456",
            "traceparent": "00-cccccccccccccccccccccccccccccccc-dddddddddddddddd-01",
        },
    )
    assert resp.status_code == 200, resp.text
    assert captured.get("request_id") == "req-456"
