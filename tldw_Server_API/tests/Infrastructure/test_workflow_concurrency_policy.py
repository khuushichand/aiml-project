from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

PR_STABLE_CONCURRENCY = "${{ github.event.pull_request.number || github.ref }}"

EXPECTED_WORKFLOW_GROUPS = {
    "ci.yml": f"ci-{PR_STABLE_CONCURRENCY}",
    "backend-required.yml": f"backend-required-{PR_STABLE_CONCURRENCY}",
    "coverage-required.yml": f"coverage-required-{PR_STABLE_CONCURRENCY}",
    "frontend-required.yml": f"frontend-required-{PR_STABLE_CONCURRENCY}",
    "security-required.yml": f"security-required-{PR_STABLE_CONCURRENCY}",
    "e2e-required.yml": f"e2e-required-{PR_STABLE_CONCURRENCY}",
    "frontend-ux-gates.yml": f"frontend-ux-gates-{PR_STABLE_CONCURRENCY}",
    "pre-commit.yml": f"pre-commit-{PR_STABLE_CONCURRENCY}",
    "pypi-package.yml": f"pypi-package-{PR_STABLE_CONCURRENCY}",
    "sbom.yml": f"sbom-{PR_STABLE_CONCURRENCY}",
}


def _load_workflow(name: str) -> dict:
    with (WORKFLOWS_DIR / name).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_target_workflows_use_pr_stable_concurrency_groups():
    for filename, expected_group in EXPECTED_WORKFLOW_GROUPS.items():
        workflow = _load_workflow(filename)
        concurrency = workflow.get("concurrency")

        assert isinstance(concurrency, dict), f"{filename} is missing a concurrency block"  # nosec B101
        assert concurrency.get("group") == expected_group  # nosec B101
        assert concurrency.get("cancel-in-progress") is True  # nosec B101
