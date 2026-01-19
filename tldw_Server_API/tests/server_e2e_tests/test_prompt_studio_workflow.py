import os
import time
from uuid import uuid4

import pytest


def _api_key() -> str:
    return os.environ.get("SINGLE_USER_API_KEY", "sk-test-1234567890-VALID")


def _auth_headers() -> dict:
    return {"X-API-KEY": _api_key()}


def _require_ok(resp, label: str) -> None:
    if not resp.ok:
        raise AssertionError(f"{label} failed: status={resp.status} body={resp.text()}")


def _poll_evaluation(page, headers: dict, evaluation_id: int, timeout_s: float = 30.0) -> dict:
    start = time.time()
    last_payload = None
    while (time.time() - start) < timeout_s:
        resp = page.request.get(
            f"/api/v1/prompt-studio/evaluations/{evaluation_id}",
            headers=headers,
        )
        if resp.ok:
            payload = resp.json()
            status = str(payload.get("status", "")).lower()
            if status in {"completed", "failed"}:
                return payload
            last_payload = payload
        time.sleep(0.5)
    raise AssertionError(f"evaluation {evaluation_id} did not complete: last={last_payload}")


@pytest.mark.e2e
def test_prompt_studio_project_prompt_eval_workflow(page, server_url):
    headers = _auth_headers()
    suffix = uuid4().hex[:8]

    project_resp = page.request.post(
        "/api/v1/prompt-studio/projects",
        headers=headers,
        json={
            "name": f"E2E PS Project {suffix}",
            "description": "Prompt Studio E2E workflow project.",
            "status": "active",
        },
    )
    _require_ok(project_resp, "create project")
    project = project_resp.json()
    project_id = project.get("id") or project.get("project_id")
    assert project_id

    prompt_resp = page.request.post(
        "/api/v1/prompt-studio/prompts",
        headers=headers,
        json={
            "project_id": project_id,
            "name": f"E2E PS Prompt {suffix}",
            "system_prompt": "You are a concise assistant.",
            "user_prompt": "Summarize: {text}",
        },
    )
    _require_ok(prompt_resp, "create prompt")
    prompt = prompt_resp.json()
    prompt_id = prompt.get("id")
    assert prompt_id

    test_case_resp = page.request.post(
        "/api/v1/prompt-studio/test-cases",
        headers=headers,
        json={
            "project_id": project_id,
            "name": f"E2E PS Case {suffix}",
            "inputs": {"text": "Hello prompt studio"},
            "expected_outputs": {"summary": "Hello prompt studio"},
            "tags": ["e2e", suffix],
            "is_golden": True,
        },
    )
    _require_ok(test_case_resp, "create test case")
    test_case = test_case_resp.json()
    test_case_id = test_case.get("id")
    assert test_case_id

    eval_resp = page.request.post(
        "/api/v1/prompt-studio/evaluations",
        headers=headers,
        json={
            "project_id": project_id,
            "prompt_id": prompt_id,
            "name": f"E2E PS Eval {suffix}",
            "description": "Prompt Studio async evaluation run.",
            "test_case_ids": [test_case_id],
            "run_async": True,
            "config": {
                "model_name": os.getenv("TLDW_E2E_PROMPT_STUDIO_MODEL", "gpt-3.5-turbo"),
                "temperature": 0.1,
                "max_tokens": 64,
            },
        },
    )
    _require_ok(eval_resp, "create evaluation")
    eval_payload = eval_resp.json()
    eval_id = eval_payload.get("id")
    assert eval_id

    eval_result = _poll_evaluation(page, headers, eval_id)
    assert eval_result.get("id") == eval_id
    assert str(eval_result.get("status", "")).lower() in {"completed", "failed"}

    stats_resp = page.request.get(
        f"/api/v1/prompt-studio/projects/stats/{project_id}",
        headers=headers,
    )
    _require_ok(stats_resp, "get project stats")
    stats_payload = stats_resp.json()
    stats = stats_payload.get("data", stats_payload)
    assert stats.get("prompt_count", 0) >= 1
    assert stats.get("test_case_count", 0) >= 1

    delete_tc = page.request.delete(
        f"/api/v1/prompt-studio/test-cases/delete/{test_case_id}",
        headers=headers,
    )
    _require_ok(delete_tc, "delete test case")

    delete_project = page.request.delete(
        f"/api/v1/prompt-studio/projects/delete/{project_id}",
        headers=headers,
    )
    _require_ok(delete_project, "delete project")
