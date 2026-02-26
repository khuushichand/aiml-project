## Stage 1: Reproduce And Isolate Root Cause
**Goal**: Confirm why critical e2e smoke tests fail in in-process single-user mode with `UserNotFoundError`.
**Success Criteria**: Captured evidence shows tests can authenticate via test API key while downstream services still require a concrete AuthNZ user row.
**Tests**: Inspect failing CI logs and trace auth/storage call paths in e2e harness and backend services.
**Status**: Complete

## Stage 2: Add Regression Coverage
**Goal**: Add a targeted e2e test proving in-process single-user setup yields an actual AuthNZ user record for `SINGLE_USER_FIXED_ID`.
**Success Criteria**: New test fails before bootstrap fix and passes after fix.
**Tests**: `pytest tldw_Server_API/tests/e2e/test_inprocess_single_user_bootstrap.py -q`
**Status**: Complete

## Stage 3: Implement Fixture-Level Bootstrap + Verify Critical Paths
**Goal**: Ensure e2e session setup bootstraps single-user profile for in-process runs, then verify previously failing critical tests.
**Success Criteria**: Targeted critical tests no longer fail with `UserNotFoundError` in local/CI-equivalent execution.
**Tests**:
- `pytest tldw_Server_API/tests/e2e/test_background_jobs_and_rate_limits.py::test_embedding_jobs_list_and_progression -q`
- `pytest tldw_Server_API/tests/e2e/test_smoke_user_journeys.py::test_smoke_basic_user_journey -q`
- plus existing CI critical-only workflow
**Status**: In Progress
