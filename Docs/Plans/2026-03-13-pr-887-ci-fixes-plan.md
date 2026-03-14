# PR 887 CI Fixes Plan

## Stage 1: Confirm Root Causes
**Goal**: Map each failing PR check to a concrete code or test issue.
**Success Criteria**: The blocking failures are categorized as backend contract bug, smoke-profile allowlist gap, or flaky/brittle frontend test.
**Tests**: Inspect GitHub Actions logs, run targeted local reproductions for the failing Characters tests.
**Status**: Complete

## Stage 2: Fix Backend Contract Regression
**Goal**: Restore a valid response payload for `GET /api/v1/admin/notes/title-settings`.
**Success Criteria**: The endpoint always returns `effective_strategy` and targeted integration coverage asserts it.
**Tests**: `python -m pytest tldw_Server_API/tests/integration/test_admin_notes_title_settings.py -v`
**Status**: Complete

## Stage 3: Fix Smoke Gate Expectations
**Goal**: Treat known minimal-smoke-profile optional endpoint 404s as allowlisted noise on the affected routes.
**Success Criteria**: The smoke harness no longer fails on recoverable 404s for family wizard, prompt studio status, collections reading probes, moderation playground, and chunking playground.
**Tests**: Targeted smoke classification verification plus the affected smoke gate command if feasible.
**Status**: Complete

## Stage 4: Stabilize Characters Harness Tests
**Goal**: Remove brittle animation/timing assumptions from the three failing Characters harness tests.
**Success Criteria**: The import preview close assertion is robust, and persona action tests have timing that reflects CI runtime.
**Tests**: `CI=true bun run test:characters-harness`
**Status**: Complete

## Stage 5: Verify and Ship
**Goal**: Re-run the affected suites, run Bandit on touched backend files, and push the fixes.
**Success Criteria**: Local targeted verification is green and the branch is pushed to PR `#887`.
**Tests**: Targeted pytest/vitest commands, smoke-focused checks if feasible, Bandit on touched backend paths.
**Status**: Complete
