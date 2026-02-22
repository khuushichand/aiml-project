# Implementation Plan: UX Audit v2 Settings Pages

## Scope

Pages: Settings and all settings subroutes  
Issue IDs: `SET-1` through `SET-7`

## Issue Grouping Coverage

- `SET-1`: Settings sidebar has 40+ items, overwhelming IA
- `SET-2`: Excessive "New" badges reduce signal
- `SET-3`: `/settings/ui` returns 404
- `SET-4`: `/settings/image-gen` returns 404
- `SET-5`: Guardian page shows deprecation warnings + 404 API errors
- `SET-6`: CSS variable swatches look developer-facing
- `SET-7`: Positive finding to preserve (System Reset destructive styling)

## Stage 1: Settings Navigation IA Cleanup
**Goal**: Make settings discoverable and manageable for non-expert users.
**Success Criteria**:
- Sidebar items are grouped and reduced to a manageable top-level set.
- "New" badges are limited to meaningful, time-bound announcements.
- Search/filter within settings is available if item count remains high.
**Tests**:
- IA regression checklist for section presence and grouping.
- Component tests for badge display rules.
**Status**: Complete

## Stage 2: Route Repair and Placeholder Strategy
**Goal**: Eliminate dead links and undefined settings routes.
**Success Criteria**:
- `/settings/ui` and `/settings/image-gen` no longer 404.
- If backend support is pending, route renders a consistent "Coming Soon" state.
- Sidebar links only point to implemented or placeholder-backed routes.
**Tests**:
- Route contract tests for all settings subpaths.
- E2E navigation test from sidebar to each settings destination.
**Status**: Complete

## Stage 3: Guardian and Advanced Controls Stabilization
**Goal**: Resolve warning-heavy and partially broken advanced settings experiences.
**Success Criteria**:
- Guardian page handles missing APIs with explicit user guidance and fallback UI.
- antd deprecation warnings in settings surfaces are removed.
- Developer-only controls (for example raw CSS variable swatches) are moved behind advanced/debug affordances.
**Tests**:
- Integration tests for guardian API success/failure scenarios.
- Console warning budget checks for settings routes.
**Status**: Complete

## Stage 4: Safety and UX Regression Guardrails
**Goal**: Preserve correct destructive-action design while refining settings UX.
**Success Criteria**:
- System Reset remains clearly destructive with confirmation protections intact.
- Refactor does not regress existing working settings flows.
- Settings documentation reflects new grouping and route behavior.
**Tests**:
- Destructive-action confirmation tests.
- Snapshot tests for critical settings panels.
**Status**: Complete

## Implementation Notes (2026-02-16)

- Settings navigation now builds from `/settings/*` routes only, includes inline filtering for large menus, and limits beta badges to explicit announcement windows.
- Added missing web wrappers for `/settings/ui`, `/settings/image-generation`, and `/settings/image-gen`.
- Added `/settings/image-gen` alias handling in shared and extension route registries.
- Guardian settings now detect unsupported API endpoints (404/405/410/501) and render explicit fallback guidance instead of noisy repeated failures.
- Guardian settings alerts now use the current antd `Alert` API shape (no deprecation warning path).
- Advanced theme token tooling is now behind an explicit “Show advanced theme tools” affordance in settings.
- Added/updated targeted tests for settings nav filtering/badge policy and guardian unsupported-endpoint fallback handling.

## Kickoff Validation (2026-02-16)

- Route availability re-check (localhost web runtime):
  - `/settings/ui` -> `200`
  - `/settings/image-gen` -> `200`
  - `/settings/image-generation` -> `200`
  - `/settings/guardian` -> `200`
  - `/settings` -> `200`
- Targeted settings component/integration tests:
  - `../packages/ui/src/components/Layouts/__tests__/settings-layout-filter.test.tsx`
  - `../packages/ui/src/components/Layouts/__tests__/settings-layout-focus-order.test.tsx`
  - `../packages/ui/src/components/Layouts/__tests__/settings-nav.guardian.test.ts`
  - `../packages/ui/src/components/Option/Settings/__tests__/GuardianSettings.test.tsx`
  - Result: `23 passed`
- Focused Playwright settings navigation rerun:
  - `e2e/workflows/settings.spec.ts --grep "Settings Navigation"`
  - Result: `8 passed`
- Test-harness alignment fix applied during kickoff:
  - Updated `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend/e2e/utils/page-objects/SettingsPage.ts` `waitForReady()` to use current settings navigation markers (`data-testid="settings-navigation"` and settings nav links) instead of a legacy form selector.

## Wave A Closeout Sync (2026-02-17)

- Stage statuses remain:
  - Stage 1: `Complete`
  - Stage 2: `Complete`
  - Stage 3: `Complete`
  - Stage 4: `Complete`
- Wave A cross-plan evidence artifacts:
  - `/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/Plans/artifacts/stage2_route_contract_check_2026-02-17_waveA_closeout.json`
  - `/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/Plans/artifacts/stage1_route_smoke_results_2026-02-17_waveA_closeout.json`
  - `/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/Plans/artifacts/admin_route_smoke_check_2026-02-17_waveA_closeout.json`
- Closeout verification snapshots:
  - Stage 2 route-contract rerun (`apps/tldw-frontend/e2e/smoke/route-contract-stage2.spec.ts`) with `TLDW_STAGE2_OUTPUT_DATE=2026-02-17` + `TLDW_STAGE2_OUTPUT_SUFFIX=waveA_closeout`: `1 passed`
  - Stage 1 route-matrix rerun (`apps/tldw-frontend/e2e/smoke/stage1-route-matrix-capture.spec.ts`): `1 passed`

## Remediation Sync (2026-02-17)

- Stage 3 deprecation cleanup follow-up completed:
  - migrated settings `Collapse.Panel` usage to `Collapse.items` in:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/Settings/ImageGenerationSettings.tsx`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/Settings/QuickIngestSettings.tsx`
  - removed now-stale smoke allowlist for `rc-collapse` children deprecation:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend/e2e/smoke/smoke.setup.ts`
- Validation evidence:
  - Stage 1 route-matrix remediation rerun artifact:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/Plans/artifacts/stage1_route_smoke_results_2026-02-17_gap_remediation.json`
  - Result snapshot:
    - `/settings/quick-ingest`: `consoleErrorCount=0`
    - `/settings/image-generation`: `consoleErrorCount=0`
