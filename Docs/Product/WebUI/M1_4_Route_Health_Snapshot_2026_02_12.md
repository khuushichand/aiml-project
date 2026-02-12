# M1.4 Route Health Snapshot - 2026-02-12

Status: Initial Baseline  
Owner: WebUI  
Roadmap Link: `Docs/Product/WebUI/WebUI_UX_Strategic_Roadmap_2026_02.md`  
Execution Plan Link: `Docs/Product/WebUI/M1_Navigation_IA_Execution_Plan_2026_02.md`

## 1) Snapshot Summary

This snapshot establishes the first M1.4 baseline for route health after alias telemetry instrumentation and key navigation smoke coverage expansion.

## 2) Baseline Metrics

| Metric | Value | Source |
|---|---|---|
| Canonical route inventory published | Yes | `Docs/Product/WebUI/M1_1_Canonical_Route_Inventory_2026_02.md` |
| Documented alias redirect routes | 19 | `Docs/Product/WebUI/M1_1_Canonical_Route_Inventory_2026_02.md` |
| Alias telemetry helper present | Yes | `apps/packages/ui/src/utils/route-alias-telemetry.ts` |
| Redirect instrumentation present | Yes | `apps/tldw-frontend/components/navigation/RouteRedirect.tsx` |
| Key navigation smoke suite section | Added | `apps/tldw-frontend/e2e/smoke/all-pages.spec.ts` |
| Wayfinding smoke suite section | Added | `apps/tldw-frontend/e2e/smoke/all-pages.spec.ts` |

## 3) Verification Evidence (This Iteration)

Validated with targeted tests:

1. `apps/packages/ui/src/utils/__tests__/route-alias-telemetry.test.ts` (3 passed)
2. `apps/tldw-frontend/__tests__/navigation/route-redirect-component.test.tsx` (3 passed)
3. `apps/tldw-frontend/__tests__/navigation/route-redirect.test.ts` (4 passed)
4. `apps/tldw-frontend/__tests__/navigation/not-found-page.test.tsx` (3 passed)
5. `apps/packages/ui/src/components/Layouts/__tests__/settings-layout-focus-order.test.tsx` (2 passed)

Smoke execution:

1. Full smoke attempt:
   - Command: `TLDW_WEB_AUTOSTART=false bunx playwright test e2e/smoke/all-pages.spec.ts --reporter=line`
   - Outcome: `140 passed`, `7 failed` (43.9s)
   - Failures:
     - `Smoke Tests - All Pages › Chat (/chat)` (missing `data-testid="chat-header"` in current run target)
     - `Smoke Tests - Key Navigation Targets › Chat (/chat)` (HTTP 404)
     - `Smoke Tests - Key Navigation Targets › Media (/media)` (HTTP 404)
     - `Smoke Tests - Key Navigation Targets › Knowledge (/knowledge)` (HTTP 404)
     - `Smoke Tests - Key Navigation Targets › Notes (/notes)` (HTTP 404)
     - `Smoke Tests - Key Navigation Targets › Prompts (/prompts)` (HTTP 404)
     - `Smoke Tests - Key Navigation Targets › TLDW Settings (/settings/tldw)` (HTTP 404)
2. Focused key-nav smoke run:
   - Command: `TLDW_WEB_AUTOSTART=false bunx playwright test e2e/smoke/all-pages.spec.ts --grep "Smoke Tests - Key Navigation Targets" --reporter=list`
   - Outcome: `1 passed`, `6 failed`
   - Passing: inventory check (`keyNavEntries` contains all expected routes)
   - Failing routes: `/chat`, `/media`, `/knowledge`, `/notes`, `/prompts`, `/settings/tldw`
   - Failure mode: HTTP `404` returned for each key route assertion in `e2e/smoke/all-pages.spec.ts`.
   - Evidence artifacts:
     - `apps/tldw-frontend/test-results/smoke-all-pages-Smoke-Test-1324f-vigation-Targets-Chat-chat--chromium/test-failed-1.png`
     - `apps/tldw-frontend/test-results/smoke-all-pages-Smoke-Test-a574d-gation-Targets-Media-media--chromium/test-failed-1.png`
     - `apps/tldw-frontend/test-results/smoke-all-pages-Smoke-Test-caf11-argets-Knowledge-knowledge--chromium/test-failed-1.png`
     - `apps/tldw-frontend/test-results/smoke-all-pages-Smoke-Test-aeb03-gation-Targets-Notes-notes--chromium/test-failed-1.png`
     - `apps/tldw-frontend/test-results/smoke-all-pages-Smoke-Test-f3a10-on-Targets-Prompts-prompts--chromium/test-failed-1.png`
     - `apps/tldw-frontend/test-results/smoke-all-pages-Smoke-Test-2431d-LDW-Settings-settings-tldw--chromium/test-failed-1.png`
3. Focused key-nav + wayfinding smoke run (post-M1.3 wayfinding checks):
   - Command: `TLDW_WEB_AUTOSTART=false bunx playwright test e2e/smoke/all-pages.spec.ts --grep "Smoke Tests - (Key Navigation Targets|Wayfinding)" --reporter=list`
   - Outcome: `1 passed`, `6 failed`, `3 skipped` (9.2s)
   - Key-nav failures unchanged: `/chat`, `/media`, `/knowledge`, `/notes`, `/prompts`, `/settings/tldw` (HTTP `404`).
   - Wayfinding block status: skipped in this runtime target because wayfinding markers/routes were unavailable from direct-route loads.

## 4) Known Gaps

- Weekly alias-usage trend data is not available until telemetry accumulates in active use.
- Key-nav smoke baseline is now recorded, but all route checks currently fail with `404`; route mapping/runtime target alignment must be corrected before deprecation decisions.
- Main smoke `Chat (/chat)` expected marker (`chat-header`) was not found in this run target and needs parity verification.
- Wayfinding smoke scenarios are now present but remain skipped until route runtime parity exposes settings and custom 404 wayfinding markers on direct navigation.

## 5) Next Snapshot Inputs

For the next weekly snapshot, include:

1. Alias-hit counts by source route (top 10).
2. Destination distribution of alias redirects.
3. Pass/fail outcome from the key-nav-target smoke block.
4. Deprecation candidate list based on low-use alias thresholds.
