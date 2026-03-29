## Stage 1: Confirm Cross-Test Root Cause
**Goal**: Reproduce the Jobs failures as cross-test state leakage rather than a general enqueue bug.
**Success Criteria**: A focused pytest sequence shows fair-share integration tests leaving a stale per-user limit that breaks a later create-job test.
**Tests**: `python -m pytest -q tldw_Server_API/tests/Jobs/test_fair_share_integration.py tldw_Server_API/tests/Jobs/test_fairness_and_renew.py::test_priority_fairness_in_acquire -q`
**Status**: Complete

## Stage 2: Add Regression Coverage
**Goal**: Add a test that proves removing `JOBS_MAX_PER_USER` should restore default fair-share behavior for later JobManager usage.
**Success Criteria**: The new regression test fails before the fix and passes after it.
**Tests**: Focused pytest on the new regression test.
**Status**: Complete

## Stage 3: Refresh Fair-Share Singleton Safely
**Goal**: Keep the Jobs fair-share singleton cheap, but rebuild it when the effective env-backed limits differ from the cached scheduler.
**Success Criteria**: Tests that set `JOBS_MAX_PER_USER` no longer poison later tests that rely on defaults.
**Tests**: Focused Jobs pytest slices that previously failed after fair-share integration tests.
**Status**: Complete

## Stage 4: Verify and Security Check
**Goal**: Run the relevant Jobs regression slices and Bandit on touched source files.
**Success Criteria**: Focused pytest passes and Bandit reports no new findings in the modified Jobs code.
**Tests**: Jobs-focused pytest slices; `python -m bandit -r <touched_paths> -f json -o /tmp/bandit_jobs_fair_share_stale_singleton.json`
**Status**: Complete
