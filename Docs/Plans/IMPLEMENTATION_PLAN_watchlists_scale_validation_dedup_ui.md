## Stage 1: Define Scale Targets and Test Matrix
**Goal**: Lock concrete scale targets and the validation matrix for large source/job workloads and operational limits.
**Success Criteria**: Agreed targets are documented (throughput, latency, memory, timeout/error budgets) and mapped to concrete automated scenarios.
**Tests**:
- Add/extend perf matrix doc references in `Docs/Product/Watchlists/Watch_IMPLEMENTATION_PLAN.md`.
- Add a small metadata test validating perf scenario registration/markers.
**Status**: Complete

### Stage 1 Output: Concrete Scale Budgets (2026-02-06)

Assumptions:
- API constraints currently enforce: list `size <= 200`, preview `limit <= 200`, preview `per_source <= 100`, CSV export `size <= 1000`.
- Perf tests must run with mocked external IO (feeds, email, chatbook, TTS) for determinism.
- Budgets are measured at API boundary (request start to response body ready), single-node local test profile.

Dataset profiles:
- `P1` (baseline): 1,000 sources, 500 jobs, 10,000 runs, 100,000 scraped items.
- `P2` (target-large): 5,000 sources, 2,000 jobs, 50,000 runs, 500,000 scraped items.
- `P3` (stress): 10,000 sources, 5,000 jobs, 100,000 runs, 1,000,000 scraped items.

Latency SLOs (P95 unless noted):
- `GET /watchlists/sources?page=&size=200` on `P2`: `<= 450ms`.
- `GET /watchlists/jobs?page=&size=200` on `P2`: `<= 400ms`.
- `GET /watchlists/runs?page=&size=200` on `P2`: `<= 700ms`.
- `GET /watchlists/jobs/{job_id}/runs?page=&size=200` on `P2`: `<= 550ms`.
- `GET /watchlists/runs/export.csv?scope=global&size=1000` on `P2`: `<= 1.8s`.
- `GET /watchlists/runs/export.csv?scope=global&include_tallies=true&tallies_mode=aggregate` on `P2`: `<= 4.5s`.
- `GET /watchlists/sources/export?type=rss` on `P3`: `<= 5.0s`.
- `POST /watchlists/jobs/{id}/preview?limit=200&per_source=100` (mocked fetch path, 20 sources): `<= 2.5s`.
- `GET /watchlists/runs/{run_id}/details?include_tallies=true&filtered_sample_max=50`: `<= 650ms`.
- `GET /watchlists/sources/{source_id}/seen?keys_limit=200`: `<= 200ms`.
- `DELETE /watchlists/sources/{source_id}/seen?clear_backoff=true`: `<= 250ms`.

Throughput targets (sustained, 2-minute window, <1% non-5xx failures):
- Runs list (`/watchlists/runs`, `size=200`): `>= 20 req/s` on `P2`.
- Jobs list (`/watchlists/jobs`, `size=200`): `>= 30 req/s` on `P2`.
- Sources list (`/watchlists/sources`, `size=200`): `>= 35 req/s` on `P2`.
- Runs CSV export (`size=1000`): `>= 2 req/s` on `P2`.

Resource budgets (single-node local test profile):
- API process RSS during scale tests: `<= 1.5 GB`.
- Per-request peak allocation for runs CSV export (`size=1000`): `<= 200 MB`.
- Per-request peak allocation for aggregate tallies export: `<= 300 MB`.
- No worker thread leakage across repeated run/list/export cycles (thread count drift `<= +2` after 200 iterations).

Reliability/error budgets:
- Scale suites must keep unexpected `5xx` rate `< 0.5%`.
- Timeout budget: `< 1%` requests exceed endpoint timeout cap.
- Deterministic pagination parity: repeated reads over stable data return identical first/last IDs and `X-Has-More` semantics.

Operational limit targets to validate:
- List endpoints reject `size > 200` with `422`.
- Preview rejects `limit > 200` and `per_source > 100` with `422`.
- CSV export rejects `size > 1000` with `422`.
- Aggregate tallies mode rejects non-global scope with `400 tallies_aggregation_global_only`.
- Dedup/seen target-user access rejects non-admin with `403 watchlists_admin_required_for_target_user`.

Validation matrix (to implement in Stage 2/3):
- Endpoint: `/watchlists/runs` | Profile: `P1/P2/P3` | Budgets: list latency + throughput | Tests: `test_perf_scenarios.py` + new API load test file.
- Endpoint: `/watchlists/runs/export.csv` | Profile: `P1/P2` | Budgets: export latency + memory | Tests: new load-oriented export tests.
- Endpoint: `/watchlists/sources/export` | Profile: `P2/P3` | Budgets: OPML export latency | Tests: extend existing OPML perf tests.
- Endpoint: `/watchlists/jobs/{id}/preview` | Profile: `P1/P2` | Budgets: preview latency + cap enforcement | Tests: preview perf/bounds additions.
- Endpoint: `/watchlists/sources/{id}/seen` (GET/DELETE) | Profile: `P1/P2` | Budgets: inspect/reset latency + auth gating | Tests: `test_dedup_seen_tools.py` extensions + UI integration tests.

## Stage 2: Broader Scale Validation (Backend/API)
**Goal**: Add broader automated scale validation for large source/job load behavior.
**Success Criteria**: Performance/load tests cover high-cardinality sources/jobs, run listing/export pressure, and prompt assembly/output generation paths with deterministic pass/fail budgets.
**Tests**:
- `tldw_Server_API/tests/Watchlists/test_perf_scenarios.py` expanded with large-source and large-job cases.
- New load-oriented test file for API-level scale paths (runs list/export/tallies and run details) using mocked fetchers/services.
- Mark tests with `@pytest.mark.performance` / `@pytest.mark.load` and enforce explicit timing/assertion thresholds.
**Status**: Complete

### Stage 2 Output (Implemented)
- Expanded `tldw_Server_API/tests/Watchlists/test_perf_scenarios.py` with high-cardinality source/job listing performance coverage.
- Added `tldw_Server_API/tests/Watchlists/test_watchlists_scale_load_api.py` covering:
  - `/watchlists/runs` listing latency + throughput sanity
  - `/watchlists/jobs/{job_id}/runs` listing latency
  - `/watchlists/runs/export.csv` global export latency
  - `/watchlists/runs/export.csv` aggregate tallies latency
  - `/watchlists/runs/{run_id}/details` latency with tallies/sample
- Marker registration guard remains in `tldw_Server_API/tests/Watchlists/test_perf_plan_metadata.py`.

## Stage 3: Operational Limits and Guardrails
**Goal**: Implement and validate operational limits behavior under stress conditions.
**Success Criteria**: Limit behavior is explicit and enforced (request caps, page/size caps, export constraints, backpressure/failure behavior), with actionable error messages.
**Tests**:
- Unit/integration tests for limit enforcement and boundary behavior (accepted vs rejected payloads).
- Regression tests for no behavior drift on existing normal-sized watchlist workflows.
**Status**: Complete

### Stage 3 Output (Implemented)
- Added `tldw_Server_API/tests/Watchlists/test_operational_limits.py` (~25 tests) covering:
  - `TestListEndpointSizeLimits`: size=200 accepted, size=201 rejected (422) for /sources, /jobs, /runs, /tags, /groups
  - `TestPreviewEndpointLimits`: limit=200/201 and per_source=100/101 boundary enforcement
  - `TestCsvExportLimits`: size=1000 accepted, size=1001 rejected (422)
  - `TestTalliesAggregationScope`: scope=global+aggregate accepted, scope=job+aggregate rejected (400)
  - `TestDedupSeenAuthGating`: own-user GET/DELETE succeeds, non-admin target_user_id returns 403, admin target_user_id succeeds
  - `TestRegressionNormalWorkflows`: default-params list calls for sources/jobs/runs return data
  - `TestPaginationParity`: repeated reads return identical first/last IDs

## Stage 4: Admin UI Surfacing for Dedup/Seen Tooling
**Goal**: Surface dedup/seen diagnostics and reset controls in the admin watchlists UI.
**Success Criteria**: Admin can inspect seen count/latest seen/backoff state and execute reset actions (seen only or seen + backoff) from UI, including target-user context where applicable.
**Tests**:
- UI component tests for display state, confirmation flow, and API error handling.
- Endpoint/UI integration tests validating `target_user_id` behavior and admin-only restrictions.
- E2E smoke for inspect + reset flow from the admin page.
**Status**: Complete

### Stage 4 Output (Implemented)
- Added TypeScript types: `SourceSeenStats`, `SourceSeenResetResponse` in `apps/packages/ui/src/types/watchlists.ts`
- Added service functions: `getSourceSeenStats`, `clearSourceSeen` in `apps/packages/ui/src/services/watchlists.ts`
- Created `SourceSeenDrawer` component in `apps/packages/ui/src/components/Option/Watchlists/SourcesTab/SourceSeenDrawer.tsx`:
  - Stats display (seen count, latest seen, backoff status badge)
  - Backoff details section (defer_until, consecutive not-modified count)
  - Recent keys scrollable list
  - Reset controls: "Clear Seen Items" and "Clear All + Reset Backoff" with Popconfirm
  - Admin section: target user ID input for inspecting other users' seen data
- Wired Eye icon button into SourcesTab actions column
- Component tests in `apps/packages/ui/src/components/Option/Watchlists/SourcesTab/__tests__/SourceSeenDrawer.test.tsx` (14 tests)

## Stage 5: Documentation, Verification, and Rollout Sign-off
**Goal**: Finalize docs/runbooks and complete end-to-end verification for rollout readiness.
**Success Criteria**: API docs, release notes, and watchlists implementation plan reflect new scale validation and admin tooling; targeted test commands pass in CI/local.
**Tests**:
- Focused watchlists suite including Stage 5 scale + dedup UI tests.
- Regression subset for watchlists outputs and scheduler integration.
**Status**: Complete

### Stage 5 Output
- Documentation updated: this file and `Docs/Product/Watchlists/Watch_IMPLEMENTATION_PLAN.md`
- All stages complete; verification commands documented below

### Verification Commands
```bash
# Stage 3: Operational limits
pytest tldw_Server_API/tests/Watchlists/test_operational_limits.py -v

# Dedup/seen backend
pytest tldw_Server_API/tests/Watchlists/test_dedup_seen_tools.py -v

# All perf/scale
pytest tldw_Server_API/tests/Watchlists/ -m "performance or load" -v

# Full watchlists suite
pytest tldw_Server_API/tests/Watchlists/ -v

# Frontend component tests
cd apps && npx vitest run --reporter=verbose -- SourceSeenDrawer
```
