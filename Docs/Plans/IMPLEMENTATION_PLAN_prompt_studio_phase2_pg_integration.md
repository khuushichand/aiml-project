## Prompt Studio Phase 2 (Postgres Integration)
**Overall Status**: Complete
**Final Tests**: `python -m pytest tldw_Server_API/tests/prompt_studio/integration/test_projects_prompts_flows.py -k postgres -v`

## Stage 1: Diagnose Postgres Prompt Studio List Failures
**Goal**: Identify likely failure points for Postgres list endpoints (projects/test cases) and fixture behavior.
**Success Criteria**: Plausible root causes documented; target fixes scoped to fixtures/connection handling.
**Tests**: Review failing tests and affected endpoints; inspect DB adapter paths.
**Status**: Complete

## Stage 2: Stabilize Postgres Test Fixtures
**Goal**: Ensure Postgres fixtures reset tables and release connections between requests.
**Success Criteria**: Table reset handles backend row adapters; dependency override closes connections per request.
**Tests**: Spot-check fixture logic; rely on Prompt Studio integration tests for verification.
**Status**: Complete

## Stage 3: Validate Postgres Integration Coverage
**Goal**: Confirm Postgres list endpoints behave correctly with shared DB scope.
**Success Criteria**: `test_project_crud_list[postgres]` and `test_test_cases_and_evaluations_flow[postgres]` pass.
**Tests**: `python -m pytest tldw_Server_API/tests/prompt_studio/integration/test_projects_prompts_flows.py -k postgres -v`
**Status**: Complete

## Stage 4: Quiet Optional sync_log Inserts
**Goal**: Avoid backend errors when sync_log table is not provisioned.
**Success Criteria**: sync_log inserts are skipped cleanly without backend error logs.
**Tests**: Run Prompt Studio integration tests and confirm logs are clean.
**Status**: Complete

## Stage 5: Normalize Evaluation Timestamp Types
**Goal**: Ensure evaluation list responses validate with datetime timestamps.
**Success Criteria**: Evaluation list responses accept datetime `completed_at` without 500s.
**Tests**: `python -m pytest tldw_Server_API/tests/prompt_studio/integration/test_projects_prompts_flows.py -k test_test_cases_and_evaluations_flow -vv`
**Status**: Complete

## Stage 6: Tolerate Missing Soft-Delete Columns
**Goal**: Avoid 500s when prompt_studio_evaluations lacks deleted/deleted_at columns.
**Success Criteria**: delete evaluation path succeeds via hard delete if soft delete columns are absent.
**Tests**: `python -m pytest tldw_Server_API/tests/prompt_studio/integration/test_projects_prompts_flows.py -k test_test_cases_and_evaluations_flow -vv`
**Status**: Complete

## Stage 7: Normalize Backend Column Names
**Goal**: Ensure backend cursor columns resolve to string names for row adapters.
**Success Criteria**: Evaluation detail retrieval no longer raises KeyError on `id`.
**Tests**: `python -m pytest tldw_Server_API/tests/prompt_studio/integration/test_projects_prompts_flows.py -k "test_test_cases_and_evaluations_flow and postgres" -vv`
**Status**: Complete
