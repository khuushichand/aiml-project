# Watchlists RC Operations Runbook (2026-02-23)

## Purpose

Operational runbook for release-candidate (RC) Watchlists quality gating using the dedicated CI workflow.

## Workflow Entry Points

- Workflow file: `.github/workflows/ui-watchlists-rc-gate.yml`
- Orchestration script: `Helper_Scripts/ci/watchlists_rc_gate.py`

## Trigger Modes

1. Automatic:
   - `push` to `release/**`
   - `push` to `rc/**`
2. Manual rerun:
   - `workflow_dispatch` from GitHub Actions UI

## Gate Scope and Decision Rule

The workflow executes these gates in sequence:

1. `test:watchlists:help`
2. `test:watchlists:onboarding`
3. `test:watchlists:uc2`
4. `test:watchlists:a11y`
5. `test:watchlists:scale`

Decision policy:

- `GO`: all gates pass.
- `NO-GO`: any gate fails.

`NO-GO` is a hard release blocker.

## Job Summary Contract

Each run writes a GitHub Job Summary containing:

1. RC metadata (`ref`, `sha`, run URL, UTC timestamp)
2. per-gate status matrix with durations
3. final decision banner (`GO` or `NO-GO`)

## Operator Procedure

1. Open the latest run of `UI Watchlists RC Gate`.
2. Review the Job Summary decision and failing gate rows (if any).
3. If `GO`, continue RC promotion workflow.
4. If `NO-GO`, open failed step logs and identify failing gate(s).
5. File remediation task referencing:
   - failing gate name,
   - failing run URL,
   - impacted RC ref/SHA.
6. Rerun using `workflow_dispatch` after remediation merges.

## Escalation Rules

1. Any `NO-GO` blocks RC promotion immediately.
2. Two consecutive `NO-GO` outcomes for the same gate require escalation to the Watchlists owner/reviewer pair from the program coordination ledger.
3. If failure is infrastructure-related (dependency install, runner outage), rerun once before opening a product regression ticket.

## Local Reproduction

From repository root:

```bash
cd apps/packages/ui
bun run test:watchlists:program
```

Direct script execution:

```bash
python3 Helper_Scripts/ci/watchlists_rc_gate.py \
  --summary-output /tmp/watchlists_rc_gate_summary.md \
  --json-output /tmp/watchlists_rc_gate_results.json
```

## Ownership

- Execution owner: active RC assignee.
- Review owner: active RC reviewer.
- Source of assignment: `Docs/Plans/IMPLEMENTATION_PLAN_watchlists_ux_review_program_coordination_index_2026_02_23.md`.
