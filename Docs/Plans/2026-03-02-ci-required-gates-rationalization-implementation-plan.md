# CI Required Gates Rationalization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve merge velocity by reducing required-gate noise and moving flaky/high-cost suites out of the blocking PR path.

**Architecture:** Define a single source of truth for required checks, then align GitHub workflows and docs around a small deterministic mandatory set. Keep broad coverage through nightly and targeted post-merge workflows.

**Tech Stack:** GitHub Actions YAML, pytest/bunx suites, repo scripts, docs.

---

### Task 1: Baseline Current Workflows and Runtime Cost

**Files:**
- Create: `Docs/Plans/2026-03-02-ci-gates-baseline.md`
- Create: `tldw_Server_API/tests/CI/test_required_gates_matrix.py`
- Reference: `.github/workflows/*.yml`

**Step 1: Write the failing test**

```python
def test_required_gate_matrix_defined_and_non_empty():
    matrix = load_required_gate_matrix()
    assert "pre-commit" in matrix
    assert "backend-required" in matrix
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/CI/test_required_gates_matrix.py -v`
Expected: FAIL because matrix file/function is missing.

**Step 3: Write minimal implementation**

```python
REQUIRED_GATES = ["pre-commit", "backend-required", "frontend-required", "security-required"]
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/CI/test_required_gates_matrix.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add Docs/Plans/2026-03-02-ci-gates-baseline.md tldw_Server_API/tests/CI/test_required_gates_matrix.py
git commit -m "test(ci): add required gate matrix baseline"
```

### Task 2: Add Gate Matrix Source of Truth and Validator

**Files:**
- Create: `.github/required-gates.json`
- Create: `Helper_Scripts/ci/validate_required_gates.py`
- Modify: `.github/workflows/ci.yml`
- Test: `tldw_Server_API/tests/CI/test_required_gates_matrix.py`

**Step 1: Write the failing test**

```python
def test_workflows_align_with_required_gates_json():
    assert validate_required_gates() == []
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/CI/test_required_gates_matrix.py::test_workflows_align_with_required_gates_json -v`
Expected: FAIL until validator exists.

**Step 3: Write minimal implementation**

```python
# validate_required_gates.py

def validate_required_gates() -> list[str]:
    return []
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/CI/test_required_gates_matrix.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add .github/required-gates.json Helper_Scripts/ci/validate_required_gates.py .github/workflows/ci.yml tldw_Server_API/tests/CI/test_required_gates_matrix.py
git commit -m "ci: add required gate source of truth and validation"
```

### Task 3: Move Flaky/Heavy Checks to Non-Blocking Schedules

**Files:**
- Modify: `.github/workflows/e2e-required.yml`
- Modify: `.github/workflows/frontend-ux-gates.yml`
- Modify: `.github/workflows/ui-watchlists-scale-gates.yml`
- Create: `.github/workflows/nightly-quality-sweep.yml`
- Test: `tldw_Server_API/tests/CI/test_required_gates_matrix.py`

**Step 1: Write the failing test**

```python
def test_non_blocking_workflows_not_listed_as_required():
    required = load_required_gate_matrix()
    assert "ui-watchlists-scale-gates" not in required
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/CI/test_required_gates_matrix.py::test_non_blocking_workflows_not_listed_as_required -v`
Expected: FAIL until matrix and workflow mapping are aligned.

**Step 3: Write minimal implementation**

```python
# Update required-gates.json and workflow triggers/schedules.
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/CI/test_required_gates_matrix.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add .github/workflows/e2e-required.yml .github/workflows/frontend-ux-gates.yml .github/workflows/ui-watchlists-scale-gates.yml .github/workflows/nightly-quality-sweep.yml .github/required-gates.json tldw_Server_API/tests/CI/test_required_gates_matrix.py
git commit -m "ci: move high-cost flaky checks to nightly non-blocking workflows"
```

### Task 4: Document and Enforce PR Gate Policy

**Files:**
- Modify: `Docs/Development/Testing.md`
- Modify: `CONTRIBUTING.md`
- Create: `Docs/Operations/CI_Gate_Policy.md`
- Modify: `.github/workflows/pre-commit.yml`

**Step 1: Write the failing test**

```python
def test_required_gate_docs_match_machine_matrix():
    assert docs_and_matrix_match()
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/CI/test_required_gates_matrix.py::test_required_gate_docs_match_machine_matrix -v`
Expected: FAIL until docs parser/check exists.

**Step 3: Write minimal implementation**

```python
# Add docs consistency check for required gate list.
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/CI/test_required_gates_matrix.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add Docs/Development/Testing.md CONTRIBUTING.md Docs/Operations/CI_Gate_Policy.md .github/workflows/pre-commit.yml tldw_Server_API/tests/CI/test_required_gates_matrix.py
git commit -m "docs(ci): codify required gate policy and enforce consistency"
```
