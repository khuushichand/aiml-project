# Watchlists Telemetry & Alerting (Foundational RC Reporting) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver a foundational Watchlists telemetry pipeline that reuses the existing metrics module, ingests onboarding milestone events, derives UC2 success from backend truth, and publishes RC telemetry reports on `release/**` + `rc/**` refs and manual dispatch.

**Architecture:** Add user-scoped onboarding telemetry persistence and summary APIs under Watchlists, then expose a unified RC summary endpoint that merges onboarding, IA telemetry, and backend-derived UC2 run/output outcomes. Register operational telemetry metrics through the existing `metrics_manager` registry. Hook frontend onboarding telemetry to best-effort backend ingest. Add a dedicated RC reporting workflow + script that evaluates thresholds in reporting-only mode and fails only on operational execution errors.

**Tech Stack:** FastAPI, Pydantic, Watchlists DB layer, existing `tldw_Server_API.app.core.Metrics.metrics_manager`, Vitest, pytest, GitHub Actions, Python CI helper scripts.

---

## Stage 1: Backend Contract (Red Tests First)
**Goal**: Lock the onboarding telemetry + RC summary API contracts before implementation.
**Success Criteria**:
- New Watchlists telemetry tests fail against missing onboarding routes and RC summary payload fields.
- Test cases define accepted/rejected ingest behavior, summary calculations, and reporting-only threshold metadata shape.
**Tests**:
- `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Watchlists/test_watchlists_onboarding_telemetry_api.py`
- `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Watchlists/test_watchlists_ia_telemetry_api.py`
**Status**: Complete

### Task 1.1: Create failing API contract tests
**Files:**
- Create: `tldw_Server_API/tests/Watchlists/test_watchlists_onboarding_telemetry_api.py`
- Modify: `tldw_Server_API/tests/Watchlists/test_watchlists_ia_telemetry_api.py` (only if RC summary needs IA shape assertions)

**Steps:**
1. Add ingest tests for `POST /api/v1/watchlists/telemetry/onboarding`:
   - valid payload accepted,
   - malformed `event_type` rejected,
   - missing `session_id` rejected.
2. Add summary tests for `GET /api/v1/watchlists/telemetry/onboarding/summary`:
   - counters and rates present,
   - timing medians computed from seeded events,
   - user scope isolation enforced.
3. Add RC summary tests for `GET /api/v1/watchlists/telemetry/rc-summary`:
   - includes onboarding block, UC2 backend truth block, IA summary block, baseline/delta block,
   - threshold flags are labeled reporting-only (`potential_breach`/`ok`).
4. Run:
   - `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Watchlists/test_watchlists_onboarding_telemetry_api.py`
5. Confirm red-state failures due to unimplemented routes/data model.

## Stage 2: DB Persistence + Aggregation (Backend Core)
**Goal**: Implement onboarding telemetry storage and summary derivation in Watchlists DB management.
**Success Criteria**:
- User-scoped onboarding events persist in SQLite/Postgres Watchlists DB.
- Summary aggregations provide setup/run/output rates and median timing values.
- Contract tests advance from route-missing failures to payload/logic assertions.
**Tests**:
- `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Watchlists/test_watchlists_onboarding_telemetry_api.py`
- `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Watchlists/test_watchlists_db_user_scope.py`
**Status**: Complete

### Task 2.1: Add onboarding telemetry schema/table support
**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Watchlists_DB.py`

**Steps:**
1. Extend both SQLite and Postgres DDL branches with `watchlist_onboarding_events` table + user/session/time indexes.
2. Add guarded migration/backfill checks (matching existing `_col_exists`/`create_tables` patterns) so existing DBs are forward-compatible.
3. Add DB methods:
   - `record_onboarding_event(...)`
   - `summarize_onboarding_events(...)`
   - helper derivation for backend UC2 run/output truth in same window (using runs/outputs tables, not frontend claims).
4. Re-run Stage 1 tests and adjust implementation until assertions pass at DB layer.

## Stage 3: Watchlists API + Metrics Module Integration
**Goal**: Expose onboarding/RC telemetry endpoints and register telemetry operation metrics via existing registry.
**Success Criteria**:
- New endpoints return typed payloads and actionable errors.
- Metrics are emitted via existing registry (`/api/v1/metrics/json`, `/api/v1/metrics/text`).
- Backend telemetry tests pass end-to-end.
**Tests**:
- `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Watchlists/test_watchlists_onboarding_telemetry_api.py`
- `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Monitoring/test_metrics_endpoints.py`
- `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Watchlists/test_watchlists_ia_telemetry_api.py`
**Status**: Complete

### Task 3.1: Implement schemas and API routes
**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/watchlists_schemas.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/watchlists.py`
- Create: `tldw_Server_API/app/core/Watchlists/watchlists_telemetry_metrics.py`

**Steps:**
1. Add Pydantic contracts for onboarding ingest/summary and RC summary response models.
2. Add routes:
   - `POST /api/v1/watchlists/telemetry/onboarding`
   - `GET /api/v1/watchlists/telemetry/onboarding/summary`
   - `GET /api/v1/watchlists/telemetry/rc-summary`
3. Register and emit metrics with existing `metrics_manager`:
   - ingest totals by result (`accepted|rejected|error`),
   - summary request totals by endpoint/status,
   - summary request duration histogram.
4. Ensure exceptions return stable API error details (`watchlists_onboarding_telemetry_*`) and do not leak internals.
5. Re-run backend test bundle until green.

## Stage 4: Frontend Telemetry Wiring (Best-Effort Ingest)
**Goal**: Keep local onboarding telemetry behavior while adding non-blocking backend event ingest.
**Success Criteria**:
- Onboarding telemetry utility posts events best-effort without UX blocking.
- Service/types support onboarding + RC summary endpoints.
- Existing onboarding telemetry tests remain green; new API-post behavior is covered.
**Tests**:
- `cd apps/packages/ui && bunx vitest run src/utils/__tests__/watchlists-onboarding-telemetry.test.ts --maxWorkers=1 --no-file-parallelism`
- `cd apps/packages/ui && bunx vitest run src/utils/__tests__/watchlists-ia-experiment-telemetry.test.ts --maxWorkers=1 --no-file-parallelism`
- `cd apps/packages/ui && bunx vitest run src/services/__tests__/watchlists-overview.test.ts --maxWorkers=1 --no-file-parallelism` (sanity on service helpers)
**Status**: Complete

### Task 4.1: Add frontend service/types + utility integration
**Files:**
- Modify: `apps/packages/ui/src/types/watchlists.ts`
- Modify: `apps/packages/ui/src/services/watchlists.ts`
- Modify: `apps/packages/ui/src/utils/watchlists-onboarding-telemetry.ts`
- Modify: `apps/packages/ui/src/utils/__tests__/watchlists-onboarding-telemetry.test.ts`

**Steps:**
1. Add/normalize types for onboarding ingest + summary + RC summary responses (remove duplicate IA telemetry declarations while touching this file).
2. Add watchlists service functions:
   - `recordWatchlistsOnboardingTelemetry(...)`
   - `fetchWatchlistsOnboardingTelemetrySummary(...)`
   - `fetchWatchlistsRcTelemetrySummary(...)`
3. Update onboarding telemetry utility to call ingest service in fire-and-forget mode after local state write.
4. Add tests to assert:
   - backend post is attempted,
   - backend post failures are swallowed (state write still succeeds).
5. Run targeted vitest commands and fix regressions.

## Stage 5: RC Telemetry Report Script + Workflow (Reporting-Only Thresholds)
**Goal**: Automate telemetry reporting for RC refs/manual dispatch with reporting-only threshold evaluation.
**Success Criteria**:
- Dedicated workflow runs on `release/**`, `rc/**`, and `workflow_dispatch`.
- Script reads live API endpoints, emits markdown summary + JSON artifact, and marks threshold state without failing on threshold breaches.
- Workflow fails only for operational failures (startup/fetch/script execution).
**Tests**:
- `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/scripts/test_watchlists_telemetry_rc_report.py`
- `actionlint .github/workflows/ui-watchlists-telemetry-rc-report.yml` (if `actionlint` available)
**Status**: Complete

### Task 5.1: Build report script and workflow
**Files:**
- Create: `Helper_Scripts/ci/watchlists_telemetry_rc_report.py`
- Create: `tldw_Server_API/tests/scripts/test_watchlists_telemetry_rc_report.py`
- Create: `.github/workflows/ui-watchlists-telemetry-rc-report.yml`

**Steps:**
1. Create script contract:
   - fetch `/api/v1/watchlists/telemetry/rc-summary`,
   - evaluate threshold checks using baseline values from `Docs/Plans/watchlists_ux_stage1_telemetry_export_summary_2026_02_23.json`,
   - emit markdown with `ok|potential_breach` status rows,
   - exit `0` for threshold breaches, non-zero only for operational errors.
2. Add red-first script tests for:
   - summary rendering shape,
   - threshold classification,
   - exit-code policy.
3. Implement workflow:
   - trigger on RC refs + manual dispatch,
   - install deps, start API server in CI-safe mode, run report script,
   - always append markdown to `$GITHUB_STEP_SUMMARY`,
   - fail job only when script reports operational failure.
4. Run script tests and workflow lint (if available).

## Stage 6: Documentation, Adoption Validation, and Security Gate
**Goal**: Publish operational guidance and verify no regressions/security findings in touched scope.
**Success Criteria**:
- Monitoring/runbook docs include new telemetry workflow and API source of truth.
- Validation bundle passes for backend + frontend + script tests.
- Bandit reports no new findings in touched Python files.
**Tests**:
- `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Watchlists/test_watchlists_onboarding_telemetry_api.py`
- `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/scripts/test_watchlists_telemetry_rc_report.py`
- `cd apps/packages/ui && bun run test:watchlists:onboarding && bun run test:watchlists:uc2`
- `source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/endpoints/watchlists.py tldw_Server_API/app/core/DB_Management/Watchlists_DB.py Helper_Scripts/ci/watchlists_telemetry_rc_report.py -f json -o /tmp/bandit_watchlists_telemetry_foundational_2026_02_23.json`
**Status**: Complete

### Task 6.1: Update runbooks + capture execution notes
**Files:**
- Modify: `Docs/Plans/WATCHLISTS_POST_RELEASE_MONITORING_PLAN_2026_02_23.md`
- Modify: `Docs/Plans/WATCHLISTS_ONBOARDING_EFFECTIVENESS_VALIDATION_RUNBOOK_2026_02_23.md`
- Modify: `Docs/Plans/WATCHLISTS_UC2_WORKFLOW_KPI_RUNBOOK_2026_02_23.md`
- Modify: `Docs/Plans/IMPLEMENTATION_PLAN_watchlists_ux_review_program_coordination_index_2026_02_23.md` (if follow-on index is updated)

**Steps:**
1. Add workflow path + reporting-only threshold semantics to runbooks.
2. Add API source references for onboarding summary and RC summary endpoints.
3. Execute full validation commands and record outcomes in this plan file under `Execution Notes`.
4. Track unresolved issues explicitly (no silent deferrals).

## Execution Notes

- 2026-02-23: Stage 1 completed with red-first API contract tests added in `tldw_Server_API/tests/Watchlists/test_watchlists_onboarding_telemetry_api.py`.
- Verification run:
  - `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Watchlists/test_watchlists_onboarding_telemetry_api.py`
  - Result: expected red state (`5 failed`) because onboarding telemetry and RC summary routes are not implemented yet (`404 Not Found`).
- Regression guard:
  - `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Watchlists/test_watchlists_ia_telemetry_api.py`
  - Result: pass (`1 passed`).
- 2026-02-23: Stage 2 completed by adding onboarding telemetry persistence and summary derivation in `tldw_Server_API/app/core/DB_Management/Watchlists_DB.py`:
  - new table/indexes: `watchlist_onboarding_events` (SQLite/Postgres DDL),
  - new methods: `record_onboarding_event(...)`, `summarize_onboarding_events(...)`, `list_completed_run_ids(...)`.
- Stage 2 verification:
  - `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Watchlists/test_watchlists_db_user_scope.py`
  - Result: pass (`3 passed`).
- 2026-02-23: Stage 3 completed by adding API + metrics integration:
  - schemas: onboarding ingest/summary + RC summary in `tldw_Server_API/app/api/v1/schemas/watchlists_schemas.py`,
  - endpoints: `/telemetry/onboarding`, `/telemetry/onboarding/summary`, `/telemetry/rc-summary` in `tldw_Server_API/app/api/v1/endpoints/watchlists.py`,
  - metrics helper module: `tldw_Server_API/app/core/Watchlists/watchlists_telemetry_metrics.py`.
- Stage 3 verification:
  - `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Watchlists/test_watchlists_onboarding_telemetry_api.py`
  - `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Watchlists/test_watchlists_ia_telemetry_api.py`
  - `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Monitoring/test_metrics_endpoints.py`
  - Result: pass (`5 passed`, `1 passed`, `3 passed`).
- 2026-02-23: Stage 4 completed by wiring best-effort frontend ingest:
  - service/types updates in `apps/packages/ui/src/services/watchlists.ts` and `apps/packages/ui/src/types/watchlists.ts`,
  - onboarding utility backend-post integration in `apps/packages/ui/src/utils/watchlists-onboarding-telemetry.ts`,
  - test updates in `apps/packages/ui/src/utils/__tests__/watchlists-onboarding-telemetry.test.ts`.
- Stage 4 verification:
  - `cd apps/packages/ui && bunx vitest run src/utils/__tests__/watchlists-onboarding-telemetry.test.ts --maxWorkers=1 --no-file-parallelism`
  - `cd apps/packages/ui && bunx vitest run src/utils/__tests__/watchlists-ia-experiment-telemetry.test.ts --maxWorkers=1 --no-file-parallelism`
  - `cd apps/packages/ui && bunx vitest run src/services/__tests__/watchlists-overview.test.ts --maxWorkers=1 --no-file-parallelism`
  - Result: pass (`4 passed`, `3 passed`, `4 passed`).
- 2026-02-23: Stage 5 completed by adding RC telemetry report automation:
  - script: `Helper_Scripts/ci/watchlists_telemetry_rc_report.py`,
  - script tests: `tldw_Server_API/tests/scripts/test_watchlists_telemetry_rc_report.py`,
  - workflow: `.github/workflows/ui-watchlists-telemetry-rc-report.yml`.
- Stage 5 verification:
  - `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/scripts/test_watchlists_telemetry_rc_report.py`
  - Result: pass (`3 passed`).
  - `actionlint .github/workflows/ui-watchlists-telemetry-rc-report.yml`
  - Result: not executed locally (`actionlint` not installed in this environment).
- 2026-02-23: Stage 6 completed by updating runbooks and executing the validation/security bundle:
  - docs updated:
    - `Docs/Plans/WATCHLISTS_POST_RELEASE_MONITORING_PLAN_2026_02_23.md`
    - `Docs/Plans/WATCHLISTS_ONBOARDING_EFFECTIVENESS_VALIDATION_RUNBOOK_2026_02_23.md`
    - `Docs/Plans/WATCHLISTS_UC2_WORKFLOW_KPI_RUNBOOK_2026_02_23.md`
  - bandit false-positive suppression:
    - `tldw_Server_API/app/api/v1/endpoints/watchlists.py` (`verify_token_async(... token_type="access")  # nosec B106`)
- Stage 6 verification:
  - `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Watchlists/test_watchlists_onboarding_telemetry_api.py`
  - Result: pass (`5 passed`).
  - `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/scripts/test_watchlists_telemetry_rc_report.py`
  - Result: pass (`3 passed`).
  - `cd apps/packages/ui && bun run test:watchlists:onboarding && bun run test:watchlists:uc2`
  - Result: pass (`24 passed` + `27 passed`).
  - `source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/endpoints/watchlists.py tldw_Server_API/app/core/DB_Management/Watchlists_DB.py Helper_Scripts/ci/watchlists_telemetry_rc_report.py -f json -o /tmp/bandit_watchlists_telemetry_foundational_2026_02_23.json`
  - Result: pass (`0 findings`; warnings only for pre-existing `nosec` comments in SQL-construction call sites).

## Exit Criteria

1. Watchlists onboarding telemetry ingest + summary endpoints are implemented and tested.
2. RC summary endpoint returns onboarding + backend UC2 + IA + baseline/delta blocks.
3. Existing metrics module exports onboarding/summary telemetry operational metrics.
4. Frontend onboarding utility sends best-effort backend telemetry while preserving local behavior.
5. Dedicated RC telemetry report workflow runs on `release/**`, `rc/**`, and manual dispatch with reporting-only threshold evaluation.
6. Docs/Operations/ runbooks are updated and validation + Bandit checks pass for touched scope.
