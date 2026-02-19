## Stage 1: Plan And Baseline
**Goal**: Capture the implementation stages for hardening Watchlists extension E2E reproducibility.
**Success Criteria**:
- A task-specific plan exists under `Docs/Plans/`.
- Stages include CI gate and runbook updates.
**Tests**:
- N/A (planning artifact).
**Status**: Complete

## Stage 2: CI Non-Skip Gate
**Goal**: Add a root GitHub Actions workflow that runs `apps/extension/tests/e2e/watchlists.spec.ts` against a real backend and fails when tests are skipped.
**Success Criteria**:
- Workflow file exists under `.github/workflows/`.
- Workflow installs extension deps, launches backend, runs the watchlists spec, and asserts skip count is zero.
- Workflow uploads test artifacts and stops backend reliably.
**Tests**:
- Workflow YAML sanity check via local file inspection.
**Status**: Complete

## Stage 3: Local Runbook Canonical Path
**Goal**: Document a canonical local command path that mirrors CI expectations.
**Success Criteria**:
- Runbook includes `nvm use --lts`.
- Runbook uses `TLDW_E2E_SERVER_URL` with explicit scheme (`http://...`).
- Runbook includes a strict no-skip verification command.
**Tests**:
- Manual command verification against local environment.
**Status**: Complete

## Stage 4: Verification And Handoff
**Goal**: Validate edits and capture any remaining follow-up.
**Success Criteria**:
- Changed files are reviewed.
- Final handoff lists exact commands and what remains (if anything).
**Tests**:
- `git diff` review for edited files.
**Status**: Complete
