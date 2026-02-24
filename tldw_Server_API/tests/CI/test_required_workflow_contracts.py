from pathlib import Path

import yaml


def _load(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def test_backend_required_has_noop_and_execute_paths() -> None:
    workflow = _load(".github/workflows/backend-required.yml")
    jobs = workflow["jobs"]
    assert "backend-required" in jobs


def test_coverage_required_is_path_conditional() -> None:
    workflow = _load(".github/workflows/coverage-required.yml")
    jobs = workflow["jobs"]
    assert "coverage-required" in jobs


def test_frontend_required_lane_exists() -> None:
    workflow = _load(".github/workflows/frontend-required.yml")
    jobs = workflow["jobs"]
    assert "frontend-required" in jobs


def test_e2e_required_lane_exists_and_is_conditional() -> None:
    workflow = _load(".github/workflows/e2e-required.yml")
    jobs = workflow["jobs"]
    assert "e2e-required" in jobs


def test_security_required_lane_exists_and_uses_threshold_policy() -> None:
    workflow = _load(".github/workflows/security-required.yml")
    jobs = workflow["jobs"]
    assert "security-required" in jobs


def test_required_gate_names_documented() -> None:
    text = Path("Docs/Development/CI_REQUIRED_GATES.md").read_text(encoding="utf-8")
    for check_name in [
        "backend-required",
        "security-required",
        "coverage-required",
        "frontend-required",
        "e2e-required",
    ]:
        assert check_name in text


def test_security_required_bandit_does_not_preempt_threshold_filter() -> None:
    workflow = _load(".github/workflows/security-required.yml")
    steps = workflow["jobs"]["security-required"]["steps"]
    bandit_steps = [step for step in steps if step.get("name") == "Run Bandit scan"]
    assert bandit_steps, "Run Bandit scan step missing"
    assert "--exit-zero" in bandit_steps[0]["run"]


def test_security_required_includes_dependency_review_gate() -> None:
    workflow = _load(".github/workflows/security-required.yml")
    steps = workflow["jobs"]["security-required"]["steps"]
    dep_review_steps = [step for step in steps if step.get("name") == "Dependency review (high/critical)"]
    assert dep_review_steps, "Dependency review step missing"
    assert dep_review_steps[0]["uses"].startswith("actions/dependency-review-action@")


def test_legacy_ci_workflow_name_remains_stable_for_branch_protection() -> None:
    workflow = _load(".github/workflows/ci.yml")
    assert workflow["name"] == "CI"
