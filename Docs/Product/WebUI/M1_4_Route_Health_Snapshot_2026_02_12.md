# M1.4 Route Health Snapshot - 2026-02-12

Status: Updated Baseline (Runtime Overlay Guard + Full Smoke Parity + Key-Nav/Wayfinding Stable + Week 2 Controlled Alias Rollup)  
Owner: WebUI  
Roadmap Link: `Docs/Product/WebUI/WebUI_UX_Strategic_Roadmap_2026_02.md`  
Execution Plan Link: `Docs/Product/WebUI/M1_Navigation_IA_Execution_Plan_2026_02.md`

## 1) Snapshot Summary

This snapshot now includes the February 13, 2026 stabilization reruns that closed the key-nav/wayfinding validation loop, re-established full-smoke parity after route-shell wayfinding updates, and added a controlled non-zero Week 2 alias-rollup capture.

## 2) Baseline Metrics

| Metric | Value | Source |
|---|---|---|
| Canonical route inventory published | Yes | `Docs/Product/WebUI/M1_1_Canonical_Route_Inventory_2026_02.md` |
| Documented alias redirect routes | 19 | `Docs/Product/WebUI/M1_1_Canonical_Route_Inventory_2026_02.md` |
| Alias telemetry helper present | Yes | `apps/packages/ui/src/utils/route-alias-telemetry.ts` |
| Redirect instrumentation present | Yes | `apps/tldw-frontend/components/navigation/RouteRedirect.tsx` |
| Alias weekly rollup helper present | Yes | `apps/packages/ui/src/utils/route-alias-telemetry.ts` |
| Key navigation smoke suite section | Added | `apps/tldw-frontend/e2e/smoke/all-pages.spec.ts` |
| Wayfinding smoke suite section | Added | `apps/tldw-frontend/e2e/smoke/all-pages.spec.ts` |
| Runtime overlay guard in smoke | Added | `apps/tldw-frontend/e2e/smoke/all-pages.spec.ts` |
| Key-nav + wayfinding focused smoke status | Passing (10/10) | `apps/tldw-frontend/e2e/smoke/all-pages.spec.ts` |
| Full smoke status (latest rerun) | Passing (150/150) | `apps/tldw-frontend/e2e/smoke/all-pages.spec.ts` |

## 3) Verification Evidence (This Iteration)

Validated with targeted tests:

1. `apps/packages/ui/src/utils/__tests__/route-alias-telemetry.test.ts` (4 passed, including rollup coverage)
2. `apps/tldw-frontend/__tests__/navigation/route-redirect-component.test.tsx` (3 passed)
3. `apps/tldw-frontend/__tests__/navigation/not-found-page.test.tsx` (3 passed)
4. `apps/packages/ui/src/components/Layouts/__tests__/settings-layout-focus-order.test.tsx` (2 passed)
5. `apps/packages/ui/src/components/Common/ChatSidebar/__tests__/shortcut-active.test.ts` (5 passed)
6. `apps/packages/ui/src/routes/__tests__/app-route-not-found.test.tsx` (2 passed)

Smoke execution (chronological):

1. Focused key-nav + wayfinding smoke rerun:
   - Command: `bunx playwright test e2e/smoke/all-pages.spec.ts --grep "Smoke Tests - (Key Navigation Targets|Wayfinding)" --reporter=line`
   - Outcome: `10 passed` (11.7s)
2. Full smoke run before selector cleanup:
   - Command: `bunx playwright test e2e/smoke/all-pages.spec.ts --reporter=line`
   - Outcome: `148 passed`, `2 failed` (1.9m)
   - Failures:
     - `Smoke Tests - All Pages › Chat (/chat)` due stale selector (`chat-header`) in inventory.
     - `Smoke Tests - All Pages › Evaluations (/evaluations)` runtime `Invalid or unexpected token`.
3. Full smoke rerun after inventory alignment:
   - Change: `/chat` expected test id updated to `chat-input` in `apps/tldw-frontend/e2e/smoke/page-inventory.ts`.
   - Command: `bunx playwright test e2e/smoke/all-pages.spec.ts --reporter=line`
   - Outcome: `150 passed` (1.6m)
4. Focused key-nav + wayfinding confirmation rerun after sidepanel fallback alignment:
   - Command: `bunx playwright test e2e/smoke/all-pages.spec.ts --grep "Smoke Tests - (Key Navigation Targets|Wayfinding)" --reporter=line`
   - Outcome: `10 passed` (11.6s)
5. Runtime-overlay guard added to smoke (body/console signatures for runtime syntax/react-child errors), then rerun validation:
   - Focused command: `bunx playwright test e2e/smoke/all-pages.spec.ts --grep "Smoke Tests - (Key Navigation Targets|Wayfinding)" --reporter=line`
   - Focused outcome: `10 passed` (11.7s)
   - Full command: `bunx playwright test e2e/smoke/all-pages.spec.ts --reporter=line`
   - Full outcome: `150 passed` (1.6m)
6. Focused key-nav + wayfinding follow-up rerun for Week 2 evidence:
   - Command: `bunx playwright test e2e/smoke/all-pages.spec.ts --grep "Smoke Tests - (Key Navigation Targets|Wayfinding)" --reporter=line`
   - Outcome: `10 passed` (11.3s)
7. Full smoke follow-up rerun after Week 2 capture:
   - Command: `bunx playwright test e2e/smoke/all-pages.spec.ts --reporter=line`
   - Outcome: `150 passed` (1.6m)

Wayfinding alignment/remediation captured in this iteration:

1. Added shell-level unknown-route recovery panel (instead of blank content area) in:
   - `apps/packages/ui/src/routes/app-route.tsx`
   - `apps/tldw-frontend/extension/routes/app-route.tsx`
2. Aligned fallback language and recovery controls with 404/redirect patterns:
   - Title: `We could not find that route`
   - Route context: `Route not found: <path>`
   - Actions: `Go to Chat`, `Open Knowledge`, `Open Media`, `Open Settings`, `Go back`
3. Added active-route clarity for sidebar shortcuts in:
   - `apps/packages/ui/src/components/Common/ChatSidebar.tsx`
   - `apps/packages/ui/src/components/Common/ChatSidebar/shortcut-active.ts`
4. Added smoke-level runtime overlay assertions to catch:
   - `Runtime Error` / `Runtime SyntaxError`
   - `Invalid or unexpected token`
   - `Objects are not valid as a React child`

## 4) Known Gaps

- Production-like weekly alias-usage trend data is still not available; Week 2 now has a controlled non-zero sample, but natural traffic is still needed for deprecation decisions.
- Full smoke is passing, but high-volume console warnings (not failing assertions) still indicate backend throttling/noise on some pages.

## 5) Week 1 Alias Rollup Baseline (2026-02-13)

Capture command:

- `bunx tsx -e "import { getRouteAliasTelemetryRollup } from '@/utils/route-alias-telemetry'; (async () => { const rollup = await getRouteAliasTelemetryRollup({ topN: 10 }); console.log(JSON.stringify(rollup)); })();"` (executed from `apps/tldw-frontend`)

Capture timestamp:

- `2026-02-13T03:29:47.844Z` (UTC)

Rollup result:

| Field | Value |
|---|---|
| `total_redirects` | `0` |
| `last_event_at` | `null` |
| `top_alias_sources` | `[]` |
| `top_destinations` | `[]` |

Interpretation:

- This establishes the empty baseline prior to controlled traffic generation.

## 6) Week 2 Controlled Alias Rollup Capture (2026-02-13)

Capture command:

- `bunx playwright test e2e/smoke/alias-rollup-capture.spec.ts --reporter=line` (executed from `apps/tldw-frontend`)

Artifact:

- `Docs/Product/WebUI/M1_4_Alias_Rollup_Week2_Controlled_2026_02_13.json`

Capture timestamp:

- `2026-02-13T04:29:19.133Z` (UTC)

Rollup result:

| Field | Value |
|---|---|
| `total_redirects` (raw) | `28` |
| `run_context.observed_redirect_multiplier` | `2` |
| `normalized_estimate.total_redirects` | `14` |
| Top alias source (normalized) | `/search` (`estimated_hits: 3`) |
| Top destination (normalized) | `/settings` (`estimated_hits: 4`) |

Interpretation:

- This is the first non-zero Week 2 telemetry snapshot and confirms alias instrumentation is recording route-source and destination distribution.
- Dev-mode duplicate redirect recording was observed (`2x` multiplier), so normalized estimates should be used for apples-to-apples trend comparisons until capture environment is stabilized.

## 7) Next Snapshot Inputs

For the next weekly snapshot, include:

1. Alias-hit counts by source route (top 10), raw and normalized where applicable.
2. Destination distribution of alias redirects.
3. Pass/fail outcome from full smoke plus focused key-nav/wayfinding slices.
4. Deprecation candidate list based on low-use alias thresholds.
5. Route-shell unknown-path fallback verification samples (desktop + mobile).
6. Week-over-week comparison across Week 1 baseline, Week 2 controlled sample, and first natural-traffic sample.
