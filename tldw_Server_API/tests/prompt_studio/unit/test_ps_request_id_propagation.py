import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


def test_ps_optimization_simple_includes_request_id_in_payload(monkeypatch):
    captured = {}

    # Monkeypatch the Prompt Studio JobManager.create_job (PS-specific)
    from tldw_Server_API.app.core.Prompt_Management.prompt_studio import job_manager as ps_jm

    def fake_create_job(self, job_type, entity_id, payload, project_id=None, priority=5, max_retries=3):  # noqa: D401
        captured["payload"] = payload
        return {"id": 777, "status": "queued"}

    monkeypatch.setattr(ps_jm.JobManager, "create_job", fake_create_job, raising=True)

    client = TestClient(app)
    r = client.post(
        "/api/v1/prompt-studio/optimizations",
        json={"prompt_id": 1, "config": {"optimizer_type": "iterative"}},
        headers={
            "X-API-KEY": "test-api-key-12345",
            "X-Request-ID": "req-ps-001",
        },
    )
    assert r.status_code == 200, r.text
    assert captured.get("payload", {}).get("request_id") == "req-ps-001"
