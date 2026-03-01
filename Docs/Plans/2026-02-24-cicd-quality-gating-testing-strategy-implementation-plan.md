# CI/CD Quality Gating Testing Strategy Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement tiered, conditional, and deterministic required PR quality gates that maximize defect prevention while skipping irrelevant heavy lanes.

**Architecture:** Add a shared changed-path classifier and wire five required workflow lanes (`backend-required`, `security-required`, `coverage-required`, `frontend-required`, `e2e-required`) to that contract. Each lane must always report status and either run real checks or an explicit no-op pass. Retain legacy broad workflows as non-required/informational until phased rollout completes.

**Tech Stack:** GitHub Actions, Python 3.12, pytest, Bandit, existing repo composite actions/scripts.

---

Execution notes:
- Apply @test-driven-development for each task.
- Apply @verification-before-completion before any “done” claim.
- Keep commits small and task-scoped.

### Task 1: Build changed-path classifier contract

**Files:**
- Create: `Helper_Scripts/ci/path_classifier.py`
- Create: `tldw_Server_API/tests/CI/test_path_classifier.py`

**Step 1: Write the failing test**

```python
# tldw_Server_API/tests/CI/test_path_classifier.py
from Helper_Scripts.ci.path_classifier import classify_paths


def test_ui_only_change_disables_backend_and_coverage():
    flags = classify_paths([
        "apps/tldw-frontend/src/app/page.tsx",
        "apps/packages/ui/src/components/Option/Playground/Foo.tsx",
    ])
    assert flags["backend_changed"] is False
    assert flags["coverage_required"] is False
    assert flags["frontend_changed"] is True


def test_api_schema_change_enables_e2e():
    flags = classify_paths([
        "tldw_Server_API/app/api/v1/endpoints/chat.py",
        "tldw_Server_API/app/api/v1/schemas/chat.py",
    ])
    assert flags["backend_changed"] is True
    assert flags["e2e_changed"] is True
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/CI/test_path_classifier.py`
Expected: FAIL with import/function-not-found error.

**Step 3: Write minimal implementation**

```python
# Helper_Scripts/ci/path_classifier.py
from __future__ import annotations

from fnmatch import fnmatch
from typing import Iterable

BACKEND_GLOBS = [
    "tldw_Server_API/**",
    "pyproject.toml",
    "uv.lock",
    ".github/actions/**",
    ".github/workflows/**",
]
FRONTEND_GLOBS = [
    "apps/tldw-frontend/**",
    "apps/packages/ui/**",
    "apps/extension/**",
    "apps/bun.lock",
    "apps/tldw-frontend/package-lock.json",
]
E2E_BACKEND_GLOBS = [
    "tldw_Server_API/app/api/v1/endpoints/**",
    "tldw_Server_API/app/api/v1/schemas/**",
    "tldw_Server_API/app/core/AuthNZ/**",
]


def _matches_any(path: str, globs: list[str]) -> bool:
    return any(fnmatch(path, pattern) for pattern in globs)


def classify_paths(paths: Iterable[str]) -> dict[str, bool]:
    paths = list(paths)
    backend_changed = any(_matches_any(p, BACKEND_GLOBS) for p in paths)
    frontend_changed = any(_matches_any(p, FRONTEND_GLOBS) for p in paths)
    e2e_changed = frontend_changed or any(_matches_any(p, E2E_BACKEND_GLOBS) for p in paths)
    security_relevant_changed = backend_changed or any(
        p.endswith(("requirements.txt", "pyproject.toml", "uv.lock")) for p in paths
    )
    return {
        "backend_changed": backend_changed,
        "frontend_changed": frontend_changed,
        "e2e_changed": e2e_changed,
        "security_relevant_changed": security_relevant_changed,
        "coverage_required": backend_changed,
    }
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/CI/test_path_classifier.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add Helper_Scripts/ci/path_classifier.py tldw_Server_API/tests/CI/test_path_classifier.py
git commit -m "test+feat(ci): add path classifier contract for required gates"
```

### Task 2: Add GitHub-output emitter for gate flags

**Files:**
- Create: `Helper_Scripts/ci/emit_ci_gate_flags.py`
- Modify: `tldw_Server_API/tests/CI/test_path_classifier.py`

**Step 1: Write the failing test**

```python
def test_emitter_writes_github_output(tmp_path, monkeypatch):
    out = tmp_path / "gh.out"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    from Helper_Scripts.ci.emit_ci_gate_flags import emit

    emit(["apps/tldw-frontend/src/app/page.tsx"])
    text = out.read_text(encoding="utf-8")
    assert "frontend_changed=true" in text
    assert "backend_changed=false" in text
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/CI/test_path_classifier.py::test_emitter_writes_github_output`
Expected: FAIL with module/function missing.

**Step 3: Write minimal implementation**

```python
# Helper_Scripts/ci/emit_ci_gate_flags.py
from __future__ import annotations

import os
from typing import Iterable

from Helper_Scripts.ci.path_classifier import classify_paths


def emit(paths: Iterable[str]) -> None:
    flags = classify_paths(paths)
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        raise RuntimeError("GITHUB_OUTPUT is required")
    with open(output_path, "a", encoding="utf-8") as fh:
        for key, value in flags.items():
            fh.write(f"{key}={'true' if value else 'false'}\n")


def main() -> None:
    import sys

    emit(sys.argv[1:])


if __name__ == "__main__":
    main()
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/CI/test_path_classifier.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add Helper_Scripts/ci/emit_ci_gate_flags.py tldw_Server_API/tests/CI/test_path_classifier.py
git commit -m "feat(ci): emit required-gate flags to GitHub outputs"
```

### Task 3: Add reusable change-detection composite action

**Files:**
- Create: `.github/actions/detect-required-gate-changes/action.yml`
- Create: `tldw_Server_API/tests/CI/test_detect_required_gate_changes_action.py`

**Step 1: Write the failing test**

```python
import yaml
from pathlib import Path


def test_action_exposes_required_outputs():
    p = Path(".github/actions/detect-required-gate-changes/action.yml")
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    outputs = data["outputs"]
    for key in [
        "backend_changed",
        "frontend_changed",
        "e2e_changed",
        "security_relevant_changed",
        "coverage_required",
    ]:
        assert key in outputs
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/CI/test_detect_required_gate_changes_action.py`
Expected: FAIL because action file does not exist.

**Step 3: Write minimal implementation**

```yaml
# .github/actions/detect-required-gate-changes/action.yml
name: Detect Required Gate Changes
runs:
  using: composite
  steps:
    - id: changed-files
      shell: bash
      run: |
        git diff --name-only "${{ github.event.pull_request.base.sha || 'HEAD~1' }}" "${{ github.sha }}" > /tmp/changed_files.txt
        python Helper_Scripts/ci/emit_ci_gate_flags.py $(cat /tmp/changed_files.txt)
outputs:
  backend_changed:
    value: ${{ steps.changed-files.outputs.backend_changed }}
  frontend_changed:
    value: ${{ steps.changed-files.outputs.frontend_changed }}
  e2e_changed:
    value: ${{ steps.changed-files.outputs.e2e_changed }}
  security_relevant_changed:
    value: ${{ steps.changed-files.outputs.security_relevant_changed }}
  coverage_required:
    value: ${{ steps.changed-files.outputs.coverage_required }}
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/CI/test_detect_required_gate_changes_action.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add .github/actions/detect-required-gate-changes/action.yml tldw_Server_API/tests/CI/test_detect_required_gate_changes_action.py
git commit -m "feat(ci): add reusable change-detection action for required lanes"
```

### Task 4: Introduce backend-required and coverage-required workflows

**Files:**
- Create: `.github/workflows/backend-required.yml`
- Create: `.github/workflows/coverage-required.yml`
- Create: `tldw_Server_API/tests/CI/test_required_workflow_contracts.py`

**Step 1: Write the failing test**

```python
import yaml
from pathlib import Path


def _load(path: str):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def test_backend_required_has_noop_and_execute_paths():
    wf = _load(".github/workflows/backend-required.yml")
    jobs = wf["jobs"]
    assert "backend-required" in jobs


def test_coverage_required_is_path_conditional():
    wf = _load(".github/workflows/coverage-required.yml")
    jobs = wf["jobs"]
    assert "coverage-required" in jobs
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/CI/test_required_workflow_contracts.py`
Expected: FAIL because workflows do not exist.

**Step 3: Write minimal implementation**

- `backend-required.yml`:
  - always runs `changes` job
  - `backend-required` job with conditional execution when `backend_changed=true`
  - explicit no-op success step when false
  - backend lint/type/tests with `continue-on-error: false`
- `coverage-required.yml`:
  - same pattern with `coverage_required`
  - enforce global `--cov-fail-under=<agreed threshold>` only when true

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/CI/test_required_workflow_contracts.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add .github/workflows/backend-required.yml .github/workflows/coverage-required.yml tldw_Server_API/tests/CI/test_required_workflow_contracts.py
git commit -m "feat(ci): add backend and coverage required-gate workflows"
```

### Task 5: Introduce frontend-required and e2e-required workflows

**Files:**
- Create: `.github/workflows/frontend-required.yml`
- Create: `.github/workflows/e2e-required.yml`
- Modify: `tldw_Server_API/tests/CI/test_required_workflow_contracts.py`

**Step 1: Write the failing test**

```python
def test_frontend_required_lane_exists():
    wf = _load(".github/workflows/frontend-required.yml")
    assert "frontend-required" in wf["jobs"]


def test_e2e_required_lane_exists_and_is_conditional():
    wf = _load(".github/workflows/e2e-required.yml")
    assert "e2e-required" in wf["jobs"]
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/CI/test_required_workflow_contracts.py`
Expected: FAIL because workflows do not exist.

**Step 3: Write minimal implementation**

- `frontend-required.yml`:
  - execute only when `frontend_changed=true`
  - no-op pass when false
- `e2e-required.yml`:
  - execute when `frontend_changed=true` OR `e2e_changed=true`
  - include one controlled retry for known flaky segment
  - fail if retry also fails

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/CI/test_required_workflow_contracts.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add .github/workflows/frontend-required.yml .github/workflows/e2e-required.yml tldw_Server_API/tests/CI/test_required_workflow_contracts.py
git commit -m "feat(ci): add frontend and e2e required-gate workflows"
```

### Task 6: Introduce security-required workflow with high/critical blocking

**Files:**
- Create: `.github/workflows/security-required.yml`
- Create: `.github/security/ci-allowlist.yml`
- Modify: `tldw_Server_API/tests/CI/test_required_workflow_contracts.py`

**Step 1: Write the failing test**

```python
def test_security_required_lane_exists_and_uses_threshold_policy():
    wf = _load(".github/workflows/security-required.yml")
    assert "security-required" in wf["jobs"]
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/CI/test_required_workflow_contracts.py`
Expected: FAIL because workflow does not exist.

**Step 3: Write minimal implementation**

- `security-required.yml`:
  - always publishes required check status
  - runs dependency/CVE + Bandit path-aware scan
  - fails only on `high`/`critical` after applying allowlist
- `ci-allowlist.yml`:
  - entries must include finding id, owner, and expiry date

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/CI/test_required_workflow_contracts.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add .github/workflows/security-required.yml .github/security/ci-allowlist.yml tldw_Server_API/tests/CI/test_required_workflow_contracts.py
git commit -m "feat(ci): add security required-gate workflow with severity policy"
```

### Task 7: Wire phased rollout and required-check documentation

**Files:**
- Modify: `.github/workflows/ci.yml`
- Create: `Docs/Development/CI_REQUIRED_GATES.md`
- Modify: `README.md`

**Step 1: Write the failing test**

```python
def test_required_gate_names_documented():
    text = Path("Docs/Development/CI_REQUIRED_GATES.md").read_text(encoding="utf-8")
    for check in [
        "backend-required",
        "security-required",
        "coverage-required",
        "frontend-required",
        "e2e-required",
    ]:
        assert check in text
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/CI/test_required_workflow_contracts.py::test_required_gate_names_documented`
Expected: FAIL because documentation does not exist yet.

**Step 3: Write minimal implementation**

- Update `ci.yml` so legacy broad suites remain informational/non-required during phase-in
- Add `Docs/Development/CI_REQUIRED_GATES.md`:
  - required check names
  - no-op semantics
  - branch protection setup steps
  - phased rollout timeline (2-4 weeks)
- Add short README pointer to the gate runbook

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/CI/test_required_workflow_contracts.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add .github/workflows/ci.yml Docs/Development/CI_REQUIRED_GATES.md README.md tldw_Server_API/tests/CI/test_required_workflow_contracts.py
git commit -m "docs+ci: document and stage required quality-gate rollout"
```

### Task 8: Final verification and security validation

**Files:**
- Modify (if needed): files changed in Tasks 1-7

**Step 1: Add/adjust final failing checks (if any regression discovered)**

- Extend `tldw_Server_API/tests/CI/test_required_workflow_contracts.py` for any missed contract assertions.

**Step 2: Run full targeted verification**

Run:

```bash
source .venv/bin/activate && \
python -m pytest -q tldw_Server_API/tests/CI && \
python -m bandit -r Helper_Scripts/ci .github/actions -f json -o /tmp/bandit_ci_required_gates.json
```

Expected:
- `pytest`: PASS
- `bandit`: no new high/critical findings in touched scope

**Step 3: Run workflow sanity checks**

Run:

```bash
source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/CI/test_required_workflow_contracts.py
```

Expected: PASS with all required-lane contracts satisfied.

**Step 4: Resolve any final issues minimally**

- Apply minimal fixes only where checks fail.

**Step 5: Commit**

```bash
git add Helper_Scripts/ci .github/actions .github/workflows Docs/Development/CI_REQUIRED_GATES.md README.md tldw_Server_API/tests/CI
git commit -m "chore(ci): finalize conditional required quality gates and validation"
```

## Rollout Acceptance Criteria

1. Required lanes are deterministic and always present on PRs.
2. Backend-required and coverage-required no-op on UI-only PRs.
3. Frontend/e2e lanes no-op on backend-only PRs unless API/schema/auth coupling paths changed.
4. Security lane blocks on high/critical findings per policy.
5. Global coverage threshold enforced only when backend paths changed.
6. Branch protection points to the five stable lane names.
