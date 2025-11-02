import uuid
import pytest


pytestmark = pytest.mark.unit


def _mk_project(client, backend_label: str) -> int:
    name = f"ValProj-{uuid.uuid4().hex[:6]} ({backend_label})"
    r = client.post("/api/v1/prompt-studio/projects/", json={"name": name, "status": "active"})
    assert r.status_code in (200, 201), r.text
    return (r.json().get("data") or r.json()).get("id")


def _mk_prompt(client, project_id: int, backend_label: str) -> int:
    r = client.post(
        "/api/v1/prompt-studio/prompts/create",
        json={
            "project_id": project_id,
            "name": f"Base-{uuid.uuid4().hex[:6]} ({backend_label})",
            "system_prompt": "S",
            "user_prompt": "{{q}}",
        },
    )
    assert r.status_code in (200, 201), r.text
    return (r.json().get("data") or {}).get("id") or r.json().get("id")


def test_iterative_and_hill_climb_pass(prompt_studio_dual_backend_client):
    backend_label, client, db = prompt_studio_dual_backend_client
    pid = _mk_project(client, backend_label)
    prompt_id = _mk_prompt(client, pid, backend_label)

    # iterative
    body = {
        "project_id": pid,
        "initial_prompt_id": prompt_id,
        "optimization_config": {
            "optimizer_type": "iterative",
            "max_iterations": 3,
            "target_metric": "accuracy",
            "early_stopping": True,
        },
        "name": "iter"
    }
    r1 = client.post("/api/v1/prompt-studio/optimizations/create", json=body)
    assert r1.status_code in (200, 201), r1.text

    # hill_climb synonym
    body["optimization_config"]["optimizer_type"] = "hill_climb"
    body["name"] = "hill"
    r2 = client.post("/api/v1/prompt-studio/optimizations/create", json=body)
    assert r2.status_code in (200, 201), r2.text


def test_grid_search_requires_models(prompt_studio_dual_backend_client):
    backend_label, client, db = prompt_studio_dual_backend_client
    pid = _mk_project(client, backend_label)
    prompt_id = _mk_prompt(client, pid, backend_label)

    bad = {
        "project_id": pid,
        "initial_prompt_id": prompt_id,
        "optimization_config": {
            "optimizer_type": "grid_search",
            "max_iterations": 2,
            "target_metric": "accuracy",
            "models_to_test": [],
        },
        "name": "grid-empty",
    }
    r_bad = client.post("/api/v1/prompt-studio/optimizations/create", json=bad)
    assert r_bad.status_code == 400

    good = {
        "project_id": pid,
        "initial_prompt_id": prompt_id,
        "optimization_config": {
            "optimizer_type": "grid_search",
            "max_iterations": 2,
            "target_metric": "accuracy",
            "models_to_test": ["gpt-4o-mini"],
        },
        "name": "grid-ok",
    }
    r_ok = client.post("/api/v1/prompt-studio/optimizations/create", json=good)
    assert r_ok.status_code in (200, 201), r_ok.text
