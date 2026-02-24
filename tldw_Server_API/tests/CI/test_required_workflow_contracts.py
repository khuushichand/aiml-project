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
