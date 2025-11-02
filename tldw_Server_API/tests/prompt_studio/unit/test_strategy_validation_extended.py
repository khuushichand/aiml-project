import uuid
import pytest


pytestmark = pytest.mark.unit


def _mk_project(client, backend_label: str) -> int:
    name = f"Val2Proj-{uuid.uuid4().hex[:6]} ({backend_label})"
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


def test_beam_search_optional_validation(prompt_studio_dual_backend_client):
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
            "strategy_params": {"beam_width": 1},  # invalid
        },
        "name": "beam-bad",
    }
    r_bad = client.post("/api/v1/prompt-studio/optimizations/create", json=bad)
    assert r_bad.status_code == 400

    good = bad.copy()
    good["optimization_config"] = dict(bad["optimization_config"], strategy_params={"beam_width": 3})
    good["name"] = "beam-good"
    r_ok = client.post("/api/v1/prompt-studio/optimizations/create", json=good)
    assert r_ok.status_code in (200, 201), r_ok.text


def test_anneal_optional_validation(prompt_studio_dual_backend_client):
    backend_label, client, db = prompt_studio_dual_backend_client
    pid = _mk_project(client, backend_label)
    prompt_id = _mk_prompt(client, pid, backend_label)

    bad = {
        "project_id": pid,
        "initial_prompt_id": prompt_id,
        "optimization_config": {
            "optimizer_type": "anneal",
            "max_iterations": 2,
            "target_metric": "accuracy",
            "strategy_params": {"cooling_rate": 1.5},  # invalid
        },
        "name": "anneal-bad",
    }
    r_bad = client.post("/api/v1/prompt-studio/optimizations/create", json=bad)
    assert r_bad.status_code == 400

    good = bad.copy()
    good["optimization_config"] = dict(bad["optimization_config"], strategy_params={"cooling_rate": 0.2, "initial_temp": 1.0})
    good["name"] = "anneal-good"
    r_ok = client.post("/api/v1/prompt-studio/optimizations/create", json=good)
    assert r_ok.status_code in (200, 201), r_ok.text


def test_genetic_optional_validation(prompt_studio_dual_backend_client):
    backend_label, client, db = prompt_studio_dual_backend_client
    pid = _mk_project(client, backend_label)
    prompt_id = _mk_prompt(client, pid, backend_label)

    bad = {
        "project_id": pid,
        "initial_prompt_id": prompt_id,
        "optimization_config": {
            "optimizer_type": "genetic",
            "max_iterations": 2,
            "target_metric": "accuracy",
            "strategy_params": {"mutation_rate": -0.1, "population_size": 1},  # invalids
        },
        "name": "genetic-bad",
    }
    r_bad = client.post("/api/v1/prompt-studio/optimizations/create", json=bad)
    assert r_bad.status_code == 400

    good = bad.copy()
    good["optimization_config"] = dict(bad["optimization_config"], strategy_params={"mutation_rate": 0.2, "population_size": 5})
    good["name"] = "genetic-good"
    r_ok = client.post("/api/v1/prompt-studio/optimizations/create", json=good)
    assert r_ok.status_code in (200, 201), r_ok.text
