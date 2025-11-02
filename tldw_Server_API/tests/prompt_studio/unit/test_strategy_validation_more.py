import uuid
import pytest


pytestmark = pytest.mark.unit


def _mk_project(client, backend_label: str) -> int:
    name = f"Val3Proj-{uuid.uuid4().hex[:6]} ({backend_label})"
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


def test_hyperparameter_validation(prompt_studio_dual_backend_client):
    backend_label, client, db = prompt_studio_dual_backend_client
    pid = _mk_project(client, backend_label)
    prompt_id = _mk_prompt(client, pid, backend_label)

    bad = {
        "project_id": pid,
        "initial_prompt_id": prompt_id,
        "optimization_config": {
            "optimizer_type": "hyperparameter",
            "max_iterations": 2,
            "target_metric": "accuracy",
            "strategy_params": {"search_method": "invalid", "params_to_optimize": []},
        },
        "name": "hyper-bad",
    }
    r_bad = client.post("/api/v1/prompt-studio/optimizations/create", json=bad)
    assert r_bad.status_code == 400

    good = {
        "project_id": pid,
        "initial_prompt_id": prompt_id,
        "optimization_config": {
            "optimizer_type": "hyperparameter",
            "max_iterations": 2,
            "target_metric": "accuracy",
            "strategy_params": {
                "search_method": "bayesian",
                "params_to_optimize": ["temperature", "max_tokens"],
                "max_trials": 5,
            },
        },
        "name": "hyper-ok",
    }
    r_ok = client.post("/api/v1/prompt-studio/optimizations/create", json=good)
    assert r_ok.status_code in (200, 201), r_ok.text


def test_random_search_trials(prompt_studio_dual_backend_client):
    backend_label, client, db = prompt_studio_dual_backend_client
    pid = _mk_project(client, backend_label)
    prompt_id = _mk_prompt(client, pid, backend_label)

    bad = {
        "project_id": pid,
        "initial_prompt_id": prompt_id,
        "optimization_config": {
            "optimizer_type": "random_search",
            "max_iterations": 2,
            "target_metric": "accuracy",
            "strategy_params": {"max_trials": 0},
        },
        "name": "rand-bad",
    }
    r_bad = client.post("/api/v1/prompt-studio/optimizations/create", json=bad)
    assert r_bad.status_code == 400

    good = bad.copy()
    good["optimization_config"] = dict(bad["optimization_config"], strategy_params={"max_trials": 5})
    good["name"] = "rand-ok"
    r_ok = client.post("/api/v1/prompt-studio/optimizations/create", json=good)
    assert r_ok.status_code in (200, 201), r_ok.text


def test_beam_search_diversity_rate(prompt_studio_dual_backend_client):
    backend_label, client, db = prompt_studio_dual_backend_client
    pid = _mk_project(client, backend_label)
    prompt_id = _mk_prompt(client, pid, backend_label)

    bad = {
        "project_id": pid,
        "initial_prompt_id": prompt_id,
        "optimization_config": {
            "optimizer_type": "beam_search",
            "max_iterations": 2,
            "target_metric": "accuracy",
            "strategy_params": {"beam_width": 3, "diversity_rate": 1.5},
        },
        "name": "beam-div-bad",
    }
    r_bad = client.post("/api/v1/prompt-studio/optimizations/create", json=bad)
    assert r_bad.status_code == 400

    good = bad.copy()
    good["optimization_config"] = dict(bad["optimization_config"], strategy_params={"beam_width": 3, "diversity_rate": 0.3})
    good["name"] = "beam-div-ok"
    r_ok = client.post("/api/v1/prompt-studio/optimizations/create", json=good)
    assert r_ok.status_code in (200, 201), r_ok.text
