## Stage 1: Reproduce Live PR Failures
**Goal**: Map each still-open PR thread/check to an exact local file and failure mode.
**Success Criteria**: Unresolved review thread, failing UX gate, failing onboarding gate, and live CodeQL alert set are all traced to concrete code paths.
**Tests**: `gh pr checks 916`, `gh api .../code-scanning/alerts?pr=916`, targeted file inspection.
**Status**: Complete

## Stage 2: Add Failing Regression Coverage
**Goal**: Capture the intended safe behavior for credentialed browser requests, splash overlay interaction, and deterministic embedding hashing before code changes.
**Success Criteria**: New or updated targeted tests fail against the current behavior for the issues being fixed.
**Tests**: targeted `vitest` and `pytest` runs on new/updated regression tests.
**Status**: In Progress

## Stage 3: Implement Focused Fixes
**Goal**: Fix the live PR issues without broad unrelated refactors.
**Success Criteria**: Browser credential policy no longer trips cross-origin notification CORS in single-user flows; onboarding CTAs are not blocked by transient overlays; weak hash and stack-trace exposure paths are removed or sanitized.
**Tests**: targeted frontend/backend unit tests plus the relevant Playwright specs.
**Status**: Not Started

## Stage 4: Verify and Push
**Goal**: Re-run the targeted suites, Bandit on touched Python code, then push and confirm PR state.
**Success Criteria**: Local targeted verification passes, diff is clean, and GitHub PR comments/checks are re-queried from the updated branch tip.
**Tests**: targeted `vitest`, `pytest`, Playwright/E2E commands, `python -m bandit -r <touched_paths>`, `git diff --check`.
**Status**: Not Started
