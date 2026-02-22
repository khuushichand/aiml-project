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


def _poll_run(page, headers: dict, run_id: str, attempts: int = 12, delay: float = 0.5) -> dict:
    last_payload = {}
    for _ in range(attempts):
        run_resp = page.request.get(f"/api/v1/evaluations/runs/{run_id}", headers=headers)
        _require_ok(run_resp, "get evaluation run")
        last_payload = run_resp.json()
        status = str(last_payload.get("status", "")).lower()
        if status in {"completed", "failed", "cancelled"}:
            return last_payload
        time.sleep(delay)
    return last_payload


@pytest.mark.e2e
def test_evaluations_exact_match_workflow(page, server_url):
    headers = _auth_headers()
    suffix = uuid4().hex[:8]

    dataset_resp = page.request.post(
        "/api/v1/evaluations/datasets",
        headers=headers,
        json={
            "name": f"e2e_dataset_{suffix}",
            "description": "E2E exact match dataset",
            "samples": [
                {
                    "input": {"output": "alpha"},
                    "expected": {"output": "alpha"},
                    "metadata": {"case": "match"},
                }
            ],
        },
    )
    _require_ok(dataset_resp, "create dataset")
    dataset_payload = dataset_resp.json()
    dataset_id = dataset_payload["id"]

    eval_resp = page.request.post(
        "/api/v1/evaluations",
        headers=headers,
        json={
            "name": f"e2e_eval_{suffix}",
            "description": "E2E exact match evaluation",
            "eval_type": "exact_match",
            "eval_spec": {
                "metrics": ["exact_match"],
                "thresholds": {"exact_match": 1.0},
            },
            "dataset_id": dataset_id,
        },
    )
    _require_ok(eval_resp, "create evaluation")
    eval_payload = eval_resp.json()
    eval_id = eval_payload["id"]

    run_resp = page.request.post(
        f"/api/v1/evaluations/{eval_id}/runs",
        headers=headers,
        json={
            "target_model": "local",
            "config": {"batch_size": 1},
        },
    )
    _require_ok(run_resp, "create evaluation run")
    run_payload = run_resp.json()
    run_id = run_payload["id"]

    final_run = _poll_run(page, headers, run_id)
    status = str(final_run.get("status", "")).lower()
    if status not in {"completed", "failed", "cancelled"}:
        cancel_resp = page.request.post(
            f"/api/v1/evaluations/runs/{run_id}/cancel",
            headers=headers,
        )
        _require_ok(cancel_resp, "cancel evaluation run")
        pytest.fail("Evaluation run did not complete in time")

    assert status == "completed"
    results = final_run.get("results") or {}
    sample_results = results.get("sample_results", [])
    assert sample_results, "Expected evaluation results"

    delete_eval = page.request.delete(f"/api/v1/evaluations/{eval_id}", headers=headers)
    assert delete_eval.status == 204

    delete_dataset = page.request.delete(f"/api/v1/evaluations/datasets/{dataset_id}", headers=headers)
    assert delete_dataset.status == 204


@pytest.mark.e2e
def test_evaluations_model_graded_external_workflow(page, server_url):
    if os.getenv("TLDW_E2E_EXTERNAL_EVALS", "").lower() not in {"1", "true", "yes", "y", "on"}:
        pytest.skip("External evals disabled; set TLDW_E2E_EXTERNAL_EVALS=1 to enable.")
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set; skipping model-graded eval workflow.")

    headers = _auth_headers()
    suffix = uuid4().hex[:8]

    dataset_resp = page.request.post(
        "/api/v1/evaluations/datasets",
        headers=headers,
        json={
            "name": f"e2e_dataset_ext_{suffix}",
            "description": "E2E model-graded dataset",
            "samples": [
                {
                    "input": {
                        "source_text": "Short source text for evaluation.",
                        "summary": "Short source text for evaluation.",
                    },
                    "expected": {},
                    "metadata": {"case": "summarization"},
                }
            ],
        },
    )
    _require_ok(dataset_resp, "create dataset (external)")
    dataset_payload = dataset_resp.json()
    dataset_id = dataset_payload["id"]

    eval_resp = page.request.post(
        "/api/v1/evaluations",
        headers=headers,
        json={
            "name": f"e2e_eval_ext_{suffix}",
            "description": "E2E model-graded evaluation",
            "eval_type": "model_graded",
            "eval_spec": {
                "sub_type": "summarization",
                "metrics": ["coherence"],
            },
            "dataset_id": dataset_id,
        },
    )
    _require_ok(eval_resp, "create evaluation (external)")
    eval_payload = eval_resp.json()
    eval_id = eval_payload["id"]

    run_resp = page.request.post(
        f"/api/v1/evaluations/{eval_id}/runs",
        headers=headers,
        json={
            "target_model": "openai",
            "config": {"batch_size": 1, "api_name": "openai"},
        },
    )
    _require_ok(run_resp, "create evaluation run (external)")
    run_payload = run_resp.json()
    run_id = run_payload["id"]

    final_run = _poll_run(page, headers, run_id, attempts=20, delay=1.0)
    status = str(final_run.get("status", "")).lower()
    if status not in {"completed", "failed", "cancelled"}:
        cancel_resp = page.request.post(
            f"/api/v1/evaluations/runs/{run_id}/cancel",
            headers=headers,
        )
        _require_ok(cancel_resp, "cancel evaluation run (external)")
        pytest.fail("External evaluation run did not complete in time")

    assert status == "completed"
    results = final_run.get("results") or {}
    sample_results = results.get("sample_results", [])
    assert sample_results

    delete_eval = page.request.delete(f"/api/v1/evaluations/{eval_id}", headers=headers)
    assert delete_eval.status == 204

    delete_dataset = page.request.delete(f"/api/v1/evaluations/datasets/{dataset_id}", headers=headers)
    assert delete_dataset.status == 204
