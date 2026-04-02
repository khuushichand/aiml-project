## Stage 1: Confirm Shared Regressions
**Goal**: Identify the common causes behind the AuthNZ `get_db_pool` errors and `app.main` reload/import failures.
**Success Criteria**: Representative failures are traced to shared fixture/module-state issues, not endpoint-specific logic.
**Tests**: Targeted pytest runs for one Postgres-backed AuthNZ test, one AuthNZ reload test, and one resource-governor claims test.
**Status**: Complete

## Stage 2: Implement Deterministic Test Bootstrap
**Goal**: Fix the missing AuthNZ fixture import and harden test-side `app.main` import/reload state handling.
**Success Criteria**: Shared fixtures no longer raise `NameError`, and test suites that reload or temporarily replace `tldw_Server_API.app.main` do so without leaving stale module/package state behind.
**Tests**: Targeted AuthNZ/Postgres fixture test, targeted AuthNZ reload tests, targeted resource-governor claims test.
**Status**: Complete

## Stage 3: Verify Affected AuthNZ Scope
**Goal**: Re-run the previously failing AuthNZ scope that exercises the shared regressions.
**Success Criteria**: The listed AuthNZ failures/errors are gone in targeted runs; Bandit shows no new findings in touched implementation files.
**Tests**: Targeted pytest commands covering failing AuthNZ tests and relevant state-mutating suites; Bandit on touched files.
**Status**: Complete
