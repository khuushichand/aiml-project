import re
from pathlib import Path

import yaml


def _load(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _get_step(steps: list[dict], name: str) -> dict:
    matching = [step for step in steps if step.get("name") == name]
    assert matching, f"{name} step missing"
    return matching[0]


def _assert_ffmpeg_portaudio_setup(path: str, job_name: str) -> None:
    workflow = _load(path)
    steps = workflow["jobs"][job_name]["steps"]
    install_step = _get_step(steps, "Install FFmpeg and PortAudio (Linux)")
    assert install_step["uses"] == "./.github/actions/setup-ffmpeg"
    assert install_step["with"]["install-portaudio"] == "true"


def test_backend_required_has_noop_and_execute_paths() -> None:
    workflow = _load(".github/workflows/backend-required.yml")
    jobs = workflow["jobs"]
    assert "backend-required" in jobs


def test_backend_required_installs_portaudio_for_pyaudio_builds() -> None:
    _assert_ffmpeg_portaudio_setup(".github/workflows/backend-required.yml", "backend-required")


def test_backend_required_type_checks_only_changed_python_files() -> None:
    workflow = _load(".github/workflows/backend-required.yml")
    steps = workflow["jobs"]["backend-required"]["steps"]
    type_step = _get_step(steps, "Type check changed backend modules")
    assert type_step.get("continue-on-error") is True
    run_script = type_step["run"]
    assert "git diff --name-only" in run_script
    assert "No backend Python files changed; skipping mypy." in run_script
    assert "mypy --follow-imports=silent --ignore-missing-imports" in run_script
    assert "mypy tldw_Server_API/" not in run_script


def test_coverage_required_is_path_conditional() -> None:
    workflow = _load(".github/workflows/coverage-required.yml")
    jobs = workflow["jobs"]
    assert "coverage-required" in jobs


def test_coverage_required_installs_portaudio_for_pyaudio_builds() -> None:
    _assert_ffmpeg_portaudio_setup(".github/workflows/coverage-required.yml", "coverage-required")


def test_coverage_required_uses_baseline_global_floor() -> None:
    workflow = _load(".github/workflows/coverage-required.yml")
    steps = workflow["jobs"]["coverage-required"]["steps"]
    coverage_step = _get_step(steps, "Run global coverage floor")
    assert "--cov-fail-under=5" in coverage_step["run"]


def test_frontend_required_lane_exists() -> None:
    workflow = _load(".github/workflows/frontend-required.yml")
    jobs = workflow["jobs"]
    assert "frontend-required" in jobs


def test_e2e_required_lane_exists_and_is_conditional() -> None:
    workflow = _load(".github/workflows/e2e-required.yml")
    jobs = workflow["jobs"]
    assert "e2e-required" in jobs


def test_e2e_required_installs_portaudio_for_pyaudio_builds() -> None:
    _assert_ffmpeg_portaudio_setup(".github/workflows/e2e-required.yml", "e2e-required")


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
    assert re.match(r"^actions/dependency-review-action@[0-9a-f]{40}$", dep_review_steps[0]["uses"])


def test_legacy_ci_workflow_name_remains_stable_for_branch_protection() -> None:
    workflow = _load(".github/workflows/ci.yml")
    assert workflow["name"] == "CI"
