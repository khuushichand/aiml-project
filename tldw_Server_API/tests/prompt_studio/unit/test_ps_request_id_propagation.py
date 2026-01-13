import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


def test_ps_optimization_simple_includes_request_id_in_payload(monkeypatch):


    captured = {}

    # Monkeypatch the Prompt Studio Jobs adapter to capture payloads
    from tldw_Server_API.app.core.Prompt_Management.prompt_studio import jobs_adapter as ps_jobs

    def fake_create_job(  # noqa: D401
        self,
        *,
        user_id=None,
        job_type=None,
        entity_id=None,
        payload=None,
        project_id=None,
        priority=5,
        max_retries=3,
        request_id=None,
        trace_id=None,
    ):
        captured["payload"] = payload
        return {"id": 777, "status": "queued"}

    monkeypatch.setattr(ps_jobs.PromptStudioJobsAdapter, "create_job", fake_create_job, raising=True)

    client = TestClient(app)
    project_resp = client.post(
        "/api/v1/prompt-studio/projects/",
        json={"name": "ReqID Project", "status": "active"},
        headers={
            "X-API-KEY": "test-api-key-12345",
        },
    )
    assert project_resp.status_code in (200, 201), project_resp.text
    project_id = (project_resp.json().get("data") or {}).get("id") or project_resp.json().get("id")

    prompt_resp = client.post(
        "/api/v1/prompt-studio/prompts/create",
        json={
            "project_id": project_id,
            "name": "ReqID Prompt",
            "system_prompt": "System",
            "user_prompt": "{{text}}",
        },
        headers={
            "X-API-KEY": "test-api-key-12345",
        },
    )
    assert prompt_resp.status_code in (200, 201), prompt_resp.text
    prompt_id = (prompt_resp.json().get("data") or {}).get("id") or prompt_resp.json().get("id")

    r = client.post(
        "/api/v1/prompt-studio/optimizations",
        json={
            "project_id": project_id,
            "prompt_id": prompt_id,
            "config": {"optimizer_type": "iterative"},
        },
        headers={
            "X-API-KEY": "test-api-key-12345",
            "X-Request-ID": "req-ps-001",
        },
    )
    assert r.status_code == 200, r.text
    assert captured.get("payload", {}).get("request_id") == "req-ps-001"
