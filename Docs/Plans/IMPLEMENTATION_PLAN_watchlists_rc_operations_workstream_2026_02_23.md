# Watchlists RC Operations Workstream Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a dedicated Watchlists RC CI gate that runs automatically on RC refs and manually on demand, fails hard on any gate failure, and publishes job-summary go/no-go output.

**Architecture:** Introduce a focused GitHub Actions workflow that delegates orchestration to a small Python driver script. The script runs each Watchlists gate sequentially, captures status/duration, emits markdown summary + JSON results, and returns a blocking exit code when any gate fails.

**Tech Stack:** GitHub Actions YAML, Python 3.12 script + pytest tests, Bun workspace scripts, existing Watchlists docs/runbooks.

---

## Stage 1: Script Contract and Test Harness
**Goal**: Define a testable contract for RC gate execution and summary output.
**Success Criteria**:
- A pytest module defines expected gate list, summary markdown structure, and pass/fail exit behavior.
- Tests fail before implementation exists.
**Tests**:
- `python -m pytest -q tldw_Server_API/tests/scripts/test_watchlists_rc_gate.py`
**Status**: Complete

### Task 1.1: Create failing tests for orchestration contract
**Files:**
- Create: `tldw_Server_API/tests/scripts/test_watchlists_rc_gate.py`
- Create: `Helper_Scripts/ci/__init__.py` (if package import support is needed)

**Steps:**
1. Write tests for:
   - exact ordered gates (`help`, `onboarding`, `uc2`, `a11y`, `scale`)
   - markdown contains RC metadata + matrix + `GO/NO-GO`
   - non-zero exit when any gate fails
2. Run:
   - `python -m pytest -q tldw_Server_API/tests/scripts/test_watchlists_rc_gate.py`
3. Confirm failure due to missing implementation.

## Stage 2: Implement RC Gate Driver Script
**Goal**: Implement the orchestration script that runs gates, writes summary, and enforces hard blocking.
**Success Criteria**:
- Script executes all gates in order and captures per-gate status/duration.
- Script writes markdown + JSON outputs.
- Script exits non-zero if any gate fails.
**Tests**:
- `python -m pytest -q tldw_Server_API/tests/scripts/test_watchlists_rc_gate.py`
**Status**: Complete

### Task 2.1: Implement minimal script to satisfy tests
**Files:**
- Create: `Helper_Scripts/ci/watchlists_rc_gate.py`

**Steps:**
1. Implement core functions:
   - gate list constant
   - runner function for one command
   - summary renderer
   - aggregate decision evaluator
2. Implement CLI entrypoint:
   - accepts output file paths for markdown/json
   - executes all gates from `apps/packages/ui`
3. Re-run tests:
   - `python -m pytest -q tldw_Server_API/tests/scripts/test_watchlists_rc_gate.py`
4. Refactor only if all tests remain green.

## Stage 3: Add Dedicated RC Workflow
**Goal**: Wire script into a new GitHub workflow with approved triggers and blocker policy.
**Success Criteria**:
- Workflow triggers on `release/**`, `rc/**`, and `workflow_dispatch`.
- Workflow installs Bun deps and executes script.
- Job summary is always appended.
- Job fails when script returns non-zero.
**Tests**:
- `actionlint .github/workflows/ui-watchlists-rc-gate.yml` (if available)
- GitHub dry-run via `workflow_dispatch`
**Status**: Complete

### Task 3.1: Author workflow YAML
**Files:**
- Create: `.github/workflows/ui-watchlists-rc-gate.yml`

**Steps:**
1. Add triggers:
   - `push` branches: `release/**`, `rc/**`
   - `workflow_dispatch`
2. Add steps:
   - checkout
   - setup Bun
   - `bun install --frozen-lockfile` in `apps/`
   - run script and capture exit code
   - append markdown file to `$GITHUB_STEP_SUMMARY` with `if: always()`
   - enforce final fail when script indicates `NO-GO`
3. Run local lint/check if available:
   - `actionlint .github/workflows/ui-watchlists-rc-gate.yml`

## Stage 4: Operational Documentation
**Goal**: Document RC operator procedure and integrate with existing Watchlists monitoring docs.
**Success Criteria**:
- New RC operations runbook exists with trigger usage, pass/fail interpretation, and escalation path.
- Monitoring plan references RC gate workflow and runbook.
**Tests**:
- `bun run test:watchlists:help` (guard against watchlists docs/test drift if touched)
- Manual doc link verification in edited files
**Status**: Complete

### Task 4.1: Create and cross-link runbook
**Files:**
- Create: `Docs/Plans/WATCHLISTS_RC_OPERATIONS_RUNBOOK_2026_02_23.md`
- Modify: `Docs/Plans/WATCHLISTS_POST_RELEASE_MONITORING_PLAN_2026_02_23.md`
- Modify: `Docs/Plans/IMPLEMENTATION_PLAN_watchlists_ux_review_program_coordination_index_2026_02_23.md` (follow-on reference entry, if appropriate)

**Steps:**
1. Add RC runbook sections:
   - trigger modes (auto/manual)
   - hard blocker policy
   - summary interpretation
   - rerun and escalation
2. Add runbook reference to monitoring plan.
3. Update coordination index with follow-on RC ops link if the program doc maintains post-closeout pointers.

## Stage 5: Verification and Security Validation
**Goal**: Produce execution evidence and ensure no new security findings in touched code.
**Success Criteria**:
- Local Watchlists program gate passes.
- New script tests pass.
- Bandit report for touched paths has no new findings.
**Tests**:
- `cd apps/packages/ui && bun run test:watchlists:program`
- `python -m pytest -q tldw_Server_API/tests/scripts/test_watchlists_rc_gate.py`
- `source .venv/bin/activate && python -m bandit Helper_Scripts/ci/watchlists_rc_gate.py -f json -o /tmp/bandit_watchlists_rc_ops_2026_02_23.json`
**Status**: Complete

### Task 5.1: Execute final validation bundle
**Files:**
- No new files required (evidence generated in CI logs and `/tmp` artifact path)

**Steps:**
1. Run the full local validation commands listed in this stage.
2. If failures occur, fix and rerun before completion.
3. Record command outcomes in:
   - `Docs/Plans/IMPLEMENTATION_PLAN_watchlists_rc_operations_workstream_2026_02_23.md` (append execution notes),
   - and/or coordination follow-on notes doc if created.

### Execution Notes (2026-02-23)

- Stage 1 completed with red-first contract tests in `tldw_Server_API/tests/scripts/test_watchlists_rc_gate.py` (expected failure before script implementation).
- Stage 2 completed with `Helper_Scripts/ci/watchlists_rc_gate.py` implementing:
  - ordered gate command list,
  - per-gate execution + duration capture,
  - markdown summary rendering,
  - `GO/NO-GO` exit behavior.
- Stage 3 completed with dedicated workflow:
  - `.github/workflows/ui-watchlists-rc-gate.yml`
  - triggers: `release/**`, `rc/**`, and `workflow_dispatch`
  - hard blocker enforcement via exit-code gate.
- Stage 3 lint note: `actionlint` is not installed in this local environment, so workflow linting must run in CI/tooling environments where `actionlint` is available.
- Stage 4 completed with runbook and cross-links:
  - `Docs/Plans/WATCHLISTS_RC_OPERATIONS_RUNBOOK_2026_02_23.md`
  - `Docs/Plans/WATCHLISTS_POST_RELEASE_MONITORING_PLAN_2026_02_23.md`
  - `Docs/Plans/IMPLEMENTATION_PLAN_watchlists_ux_review_program_coordination_index_2026_02_23.md`
- Stage 5 validation evidence:
  - `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/scripts/test_watchlists_rc_gate.py`
  - `cd apps/packages/ui && bun run test:watchlists:program`
  - `source .venv/bin/activate && python -m bandit Helper_Scripts/ci/watchlists_rc_gate.py -f json -o /tmp/bandit_watchlists_rc_ops_2026_02_23.json`
  - `/tmp/bandit_watchlists_rc_ops_2026_02_23.json` recorded zero findings.

## Exit Criteria

1. RC workflow exists and is triggerable via both RC refs and manual dispatch.
2. Any failed Watchlists gate produces `NO-GO` and failing workflow status.
3. Job summary includes per-gate matrix and final decision.
4. RC operations runbook is published and linked from monitoring plan.
5. Validation and Bandit evidence are captured with no unresolved blockers.
