# Watchlists RC Operations Design (2026-02-23)

## Scope

Define a dedicated release-candidate (RC) operations workflow for Watchlists UX quality gates that:

- Runs automatically on RC refs (`release/**`, `rc/**`) and can be rerun manually (`workflow_dispatch`).
- Blocks RC readiness on any Watchlists gate failure.
- Publishes results in GitHub Job Summary only (no PR comment requirement and no artifact requirement for this first iteration).

## Context

Program Stage 5 closeout established a unified local gate:

- `bun run test:watchlists:program`

The follow-on operational gap is CI enforcement at RC time with standardized go/no-go reporting.

## Goals

1. Enforce Watchlists release readiness at RC time with a dedicated CI workflow.
2. Provide human-readable pass/fail matrix and go/no-go decision in Job Summary.
3. Keep implementation simple and maintainable, without coupling to unrelated frontend UX workflows.

## Non-Goals

1. No PR comment bot integration in this phase.
2. No telemetry export automation in this phase.
3. No cross-product gate consolidation beyond Watchlists scope.

## Proposed Architecture

### 1) Dedicated Workflow

Create:

- `.github/workflows/ui-watchlists-rc-gate.yml`

Trigger model:

- `push` on `release/**` and `rc/**`
- `workflow_dispatch`

Execution model:

- Single job, Ubuntu runner.
- Setup Bun and install workspace dependencies from `apps/`.
- Run Watchlists gates in explicit sequence and continue gathering results even if one gate fails.
- Append standardized markdown summary to `$GITHUB_STEP_SUMMARY`.
- Fail the job at the end if any gate failed (hard blocker).

### 2) RC Gate Driver Script

Create:

- `Helper_Scripts/ci/watchlists_rc_gate.py`

Purpose:

- Centralize execution/result handling instead of embedding complex bash in YAML.
- Execute each gate command in order:
  - `bun run test:watchlists:help`
  - `bun run test:watchlists:onboarding`
  - `bun run test:watchlists:uc2`
  - `bun run test:watchlists:a11y`
  - `bun run test:watchlists:scale`
- Emit:
  - structured JSON result file (for internal step consumption),
  - markdown summary file for job summary append.
- Exit code:
  - `0` only when all gates pass,
  - non-zero when any gate fails.

This makes behavior testable with pytest and keeps workflow YAML concise.

## Data Flow

1. GitHub trigger fires workflow (auto or manual).
2. Workflow prepares Bun environment and dependencies.
3. Workflow calls `python3 Helper_Scripts/ci/watchlists_rc_gate.py`.
4. Script executes each gate and records per-gate status/duration.
5. Workflow appends generated markdown to `$GITHUB_STEP_SUMMARY`.
6. Workflow exits pass/fail according to script return code.

## Reporting Contract (Job Summary Only)

Summary sections:

1. RC metadata (ref, SHA, run URL, UTC timestamp).
2. Gate matrix (gate name, status, duration).
3. Decision banner:
   - `GO` when all pass,
   - `NO-GO` when any fail.
4. Failure note with direct instruction to inspect failed step logs.

## Failure Handling

1. Dependency/setup failures: workflow fails immediately; summary step still runs using partial context when possible.
2. Gate failures: continue through remaining gates for full matrix visibility; final decision is `NO-GO`.
3. Summary generation failure: treated as workflow failure (operational reporting is required for RC gate).

## Validation Strategy

### Local

- `cd apps/packages/ui && bun run test:watchlists:program`
- `python -m pytest -q tldw_Server_API/tests/scripts/test_watchlists_rc_gate.py` (new)

### CI

1. Manual dispatch on a test branch.
2. Push to `rc/<name>` to validate automatic trigger.
3. Confirm hard-fail behavior by intentionally breaking one gate in a test branch (dry run scenario).

## Documentation Updates

1. Add dedicated RC runbook:
   - `Docs/Plans/WATCHLISTS_RC_OPERATIONS_RUNBOOK_2026_02_23.md`
2. Link this runbook from:
   - `Docs/Plans/WATCHLISTS_POST_RELEASE_MONITORING_PLAN_2026_02_23.md`
   - `Docs/Plans/IMPLEMENTATION_PLAN_watchlists_ux_review_program_coordination_index_2026_02_23.md` (follow-on references section, if maintained)

## Risks and Mitigations

1. Risk: CI duration increases.
   - Mitigation: Keep scope limited to existing Watchlists suite; avoid duplicative jobs.
2. Risk: false negatives from infra flakes.
   - Mitigation: separate setup failures from test failures in summary; allow manual rerun entrypoint.
3. Risk: script drift from package scripts.
   - Mitigation: keep gate command list in one constant and cover with contract tests.

## Rollout

1. Merge workflow in monitoring mode on one RC cycle.
2. Validate output format with release reviewer.
3. Keep hard-blocking enabled by default per approved policy.
