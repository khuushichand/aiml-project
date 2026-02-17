# Implementation Plan: UX Audit v2 Admin Pages

## Scope

Pages: Admin, Admin Server, Admin Llama.cpp, Admin MLX, related admin subroutes  
Issue IDs: `ADMIN-1`, `ADMIN-2`, `ADMIN-3`, `ADMIN-4`, `ADMIN-5`, `LLAMA-1`, `LLAMA-2`, `MLX-1`

## Issue Grouping Coverage

- `ADMIN-1`: System statistics skeletons never resolve
- `ADMIN-2`: Raw byte values need human-readable formatting
- `ADMIN-3`: Retry-after seconds need relative-time formatting
- `ADMIN-4`: Delete action lacks confirmation safeguard
- `ADMIN-5`: Multiple admin subroutes show same page content
- `LLAMA-1`: Error message leaks raw API/config paths
- `LLAMA-2`: Interactive form shown despite missing backend configuration
- `MLX-1`: Inactive status vs concurrency value is unclear

## Stage 1: Admin Routing Correctness
**Goal**: Ensure each admin subroute maps to intended content or explicit placeholder.
**Success Criteria**:
- Data Ops and watchlist admin routes no longer collapse into generic server page.
- Subroute headers, breadcrumbs, and content are route-specific.
- Misrouting regressions are caught by automated route assertions.
**Tests**:
- Admin route contract integration tests.
- E2E navigation tests across all admin sidebar items.
**Status**: Complete

## Stage 2: Data Load and Presentation Reliability
**Goal**: Resolve unresolved loaders and improve metric readability.
**Success Criteria**:
- Statistics loaders transition to data or explicit error/retry state.
- Byte and duration values are formatted for human comprehension.
- MLX status messaging clarifies meaning of inactive/concurrency indicators.
**Tests**:
- Unit tests for formatting utilities (bytes, duration, retry windows).
- Integration tests for admin metrics success/failure/timeout paths.
**Status**: Complete

## Stage 3: Safety and Capability Gating
**Goal**: Prevent unsafe or guaranteed-failure admin actions.
**Success Criteria**:
- Destructive actions require confirmation with clear impact messaging.
- Provider forms are disabled or gated when backend prerequisites are missing.
- Errors expose actionable guidance without internal path leakage.
**Tests**:
- Destructive-action confirmation tests.
- Capability-detection tests for llama/mlx configuration states.
- Redaction tests for admin error messages.
**Status**: Complete

## Stage 4: Operational UX Regression Hardening
**Goal**: Keep admin surfaces trustworthy for operators.
**Success Criteria**:
- Admin pages remain functional under partial backend outages.
- Console warnings on admin pages are reduced to agreed baseline.
- Admin troubleshooting docs align with updated UI behavior.
**Tests**:
- Fault-injection integration tests for 404/429/503 API responses.
- Playwright smoke run for admin health checks.
**Status**: Complete

## Implementation Notes (2026-02-16)

- Admin misrouting recovery is enforced through route placeholders for:
  - `/admin/data-ops`
  - `/admin/watchlists-runs`
  - `/admin/watchlists-items`
  - plus `/admin/orgs` and `/admin/maintenance` hardening placeholders.
- Server admin budget diagnostics now use human-readable formatting:
  - bytes displayed as `KiB/MiB/GiB` instead of raw integers,
  - retry-after displayed as approximate human time (for example `~1h 4m`).
- Admin error handling was hardened with shared sanitization and guard derivation:
  - redacts raw API and filesystem paths from user-facing error surfaces,
  - treats `403` as forbidden and `404/405/410/501/503` as unavailable admin APIs.
- Llama.cpp and MLX admin routes now apply the same guard derivation and error sanitization path.
- MLX status now clarifies concurrency semantics while inactive.
- Destructive custom-role deletion in Server Admin remains confirmation-gated (`Popconfirm`) with explicit impact copy.

## Kickoff Validation (2026-02-16)

- Route correctness contract:
  - Playwright `e2e/smoke/route-contract-stage2.spec.ts` -> `1 passed`.
- Admin route smoke:
  - Playwright `e2e/smoke/all-pages.spec.ts --grep "/admin"` -> `9 passed`.
- Admin component/integration tests:
  - `../packages/ui/src/components/Option/Admin/__tests__/admin-error-utils.test.ts` (`3 passed`)
  - `../packages/ui/src/components/Option/Admin/__tests__/ServerAdminPage.media-budget.test.tsx` (`2 passed`)
  - `../packages/ui/src/components/Option/Admin/__tests__/LlamacppAdminPage.test.tsx` (`3 passed`)
  - `../packages/ui/src/components/Option/Admin/__tests__/MlxAdminPage.test.tsx` (`2 passed`)
  - Combined result: `10 passed`.

## Wave A Closeout Validation (2026-02-17)

- Admin route contract rerun:
  - Playwright: `apps/tldw-frontend/e2e/smoke/route-contract-stage2.spec.ts`
  - Command env: `TLDW_STAGE2_OUTPUT_DATE=2026-02-17 TLDW_STAGE2_OUTPUT_SUFFIX=waveA_closeout`
  - Result: `1 passed`
  - Artifact: `/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/Plans/artifacts/stage2_route_contract_check_2026-02-17_waveA_closeout.json`
- Cross-cutting route smoke rerun:
  - Playwright: `apps/tldw-frontend/e2e/smoke/stage1-route-matrix-capture.spec.ts`
  - Command env: `TLDW_STAGE1_OUTPUT_DATE=2026-02-17 TLDW_STAGE1_OUTPUT_SUFFIX=waveA_closeout`
  - Result: `1 passed`
  - Artifact: `/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/Plans/artifacts/stage1_route_smoke_results_2026-02-17_waveA_closeout.json`
  - Summary: `86` routes scanned, `0` runtime overlays, `0` template leak routes.
- Admin route smoke rerun:
  - Playwright: `apps/tldw-frontend/e2e/smoke/all-pages.spec.ts --grep "/admin" --workers=1`
  - Result: `9 passed`
  - Artifact: `/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/Plans/artifacts/admin_route_smoke_check_2026-02-17_waveA_closeout.json`
  - Note: parallel-worker run initially surfaced an intermittent Next/Turbopack runtime syntax overlay on `/admin/watchlists-items`; smoke harness now performs a bounded transient-runtime retry and the parallel rerun is clean.
- Admin route smoke rerun after harness hardening:
  - Playwright: `apps/tldw-frontend/e2e/smoke/all-pages.spec.ts --grep "/admin" --reporter=line`
  - Result: `9 passed`
  - Hardening: `apps/tldw-frontend/e2e/smoke/all-pages.spec.ts` now retries transient runtime syntax overlays once before failing.
- Admin Stage 2/3 targeted regression rerun:
  - Vitest:
    - `apps/packages/ui/src/components/Option/Admin/__tests__/admin-error-utils.test.ts`
    - `apps/packages/ui/src/components/Option/Admin/__tests__/StatusBanner.test.tsx`
    - `apps/packages/ui/src/components/Option/Admin/__tests__/ServerAdminPage.media-budget.test.tsx`
    - `apps/packages/ui/src/components/Option/Admin/__tests__/LlamacppAdminPage.test.tsx`
    - `apps/packages/ui/src/components/Option/Admin/__tests__/MlxAdminPage.test.tsx`
  - Result: `14 passed`
