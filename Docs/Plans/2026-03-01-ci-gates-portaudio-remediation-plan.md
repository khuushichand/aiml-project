## Stage 1: Confirm Root Cause
**Goal**: Identify why the three failing gates failed in GitHub Actions.
**Success Criteria**: Failure snippet and causal dependency identified from logs.
**Tests**: Inspect failed job logs for `Onboarding E2E Gate`, `UX Smoke Gate`, and `onboarding-docs-gate`.
**Status**: Complete

## Stage 2: Workflow Remediation
**Goal**: Add missing system dependency installation for PortAudio before Python dependency install in impacted workflows.
**Success Criteria**: Workflows include a deterministic setup step equivalent to passing gates.
**Tests**: Diff review of `.github/workflows/frontend-ux-gates.yml` and `.github/workflows/onboarding-docs-gate.yml`.
**Status**: In Progress

## Stage 3: Verification
**Goal**: Ensure edits are syntactically valid and do not introduce obvious security issues.
**Success Criteria**: YAML parse check passes; Bandit scan on touched scope reports no new findings.
**Tests**: Local YAML parse script and `python -m bandit -r .github/workflows -f json`.
**Status**: Not Started

## Stage 4: Report and Next Actions
**Goal**: Provide concise summary with exact changed files and recommended follow-up.
**Success Criteria**: User receives actionable next steps (push, rerun checks).
**Tests**: N/A
**Status**: Not Started
