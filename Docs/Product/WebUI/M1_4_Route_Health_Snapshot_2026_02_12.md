# M1.4 Route Health Snapshot - 2026-02-12

Status: Updated Baseline (Runtime Overlay Guard + Full Smoke Parity + Key-Nav/Wayfinding Stable + Route-Boundary Slice Stable + Invalid-Key Degradation Gate Stable + Post-M3.3 Toolbar/Component Regression Stable + Post-All-Theme-Hard-Gate Regression Stable + Week 2 Controlled Alias Rollup + Week 3 Passive Natural Sample)  
Owner: WebUI  
Roadmap Link: `Docs/Product/WebUI/WebUI_UX_Strategic_Roadmap_2026_02.md`  
Execution Plan Link: `Docs/Product/WebUI/M1_Navigation_IA_Execution_Plan_2026_02.md`

## 1) Snapshot Summary

This snapshot now includes the February 13, 2026 stabilization reruns that closed the key-nav/wayfinding validation loop, re-established full-smoke parity after route-shell wayfinding updates, added a controlled non-zero Week 2 alias-rollup capture, added the first passive Week 3 natural-sample capture, reconfirmed the combined key-nav/wayfinding/route-boundary smoke slice after M3 baseline updates, revalidated that slice plus invalid-key degradation after M3.3 toolbar/component focus updates, and reconfirmed both slices after all-theme contrast hard-gate promotion.

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
| Key-nav + wayfinding + route-boundary smoke status | Passing (25/25) | `apps/tldw-frontend/e2e/smoke/all-pages.spec.ts` |
| Key-nav + route-boundary + invalid-key degradation gate | Passing (23/23) | `apps/tldw-frontend/e2e/smoke/all-pages.spec.ts`, `apps/tldw-frontend/e2e/smoke/invalid-api-key.spec.ts` |
| Invalid-key degradation smoke status (standalone) | Passing (1/1) | `apps/tldw-frontend/e2e/smoke/invalid-api-key.spec.ts` |
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
8. M1.2 closeout focused rerun (key-nav + wayfinding):
   - Command: `bunx playwright test e2e/smoke/all-pages.spec.ts --grep "Smoke Tests - (Key Navigation Targets|Wayfinding)" --reporter=line`
   - Outcome: `10 passed` (13.4s)
9. M1.2 closeout full smoke rerun:
   - Command: `bunx playwright test e2e/smoke/all-pages.spec.ts --reporter=line`
   - Outcome: `150 passed` (1.8m)
10. Week 3 passive natural alias rollup capture:
   - Command: `bunx playwright test e2e/smoke/alias-rollup-natural-capture.spec.ts --reporter=line`
   - Outcome: `1 passed` (2.3s), artifact updated at `Docs/Product/WebUI/M1_4_Alias_Rollup_Week3_Natural_2026_02_13.json`
11. Expanded non-core forced-error route-boundary slice:
   - Command: `bunx playwright test e2e/smoke/all-pages.spec.ts --grep "Smoke Tests - Route Error Boundaries" --reporter=line`
   - Outcome: `15 passed` (22.4s)
12. Combined key-nav + wayfinding + expanded route-boundary rerun:
   - Command: `bunx playwright test e2e/smoke/all-pages.spec.ts --grep "Smoke Tests - (Key Navigation Targets|Wayfinding|Route Error Boundaries)" --reporter=line`
   - Outcome: `25 passed` (30.5s)
13. Post-M3 baseline reconfirmation rerun (same targeted smoke slice):
   - Command: `bunx playwright test e2e/smoke/all-pages.spec.ts --grep "Key Navigation|Wayfinding|Route Error Boundaries" --reporter=line`
   - Outcome: `25 passed` (31.2s)
14. Post-modal focus-contract update rerun (same targeted smoke slice):
   - Command: `bunx playwright test e2e/smoke/all-pages.spec.ts --grep "Key Navigation|Wayfinding|Route Error Boundaries" --reporter=line`
   - Outcome: `25 passed` (29.5s)
15. Combined key-nav + route-boundary + invalid-key degradation gate rerun:
   - Command: `bunx playwright test e2e/smoke/all-pages.spec.ts e2e/smoke/invalid-api-key.spec.ts --grep "Key Navigation Targets|Route Error Boundaries|Auth Error Degradation" --reporter=line`
   - Outcome: `23 passed` (29.0s)
16. Post-M3.3 toolbar/component focus rerun (key-nav + wayfinding + route-boundary):
   - Command: `bunx playwright test e2e/smoke/all-pages.spec.ts --grep "Key Navigation Targets|Wayfinding|Route Error Boundaries" --reporter=line`
   - Outcome: `25 passed` (31.5s)
17. Post-M3.3 auth degradation rerun:
   - Command: `bunx playwright test e2e/smoke/invalid-api-key.spec.ts --reporter=line`
   - Outcome: `1 passed` (3.5s)
18. Post all-theme hard-gate promotion rerun (key-nav + wayfinding + route-boundary):
   - Command: `bunx playwright test e2e/smoke/all-pages.spec.ts --grep "Key Navigation Targets|Wayfinding|Route Error Boundaries" --reporter=line`
   - Outcome: `25 passed` (31.8s)
19. Post all-theme hard-gate promotion auth degradation rerun:
   - Command: `bunx playwright test e2e/smoke/invalid-api-key.spec.ts --reporter=line`
   - Outcome: `1 passed` (3.3s)

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

- Natural-sample telemetry has now been captured, but it remains zero in passive capture context; non-zero natural traffic is still needed to execute alias retirements with confidence.
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

## 7) Week 3 Passive Natural Alias Rollup Capture (2026-02-13)

Capture command:

- `bunx playwright test e2e/smoke/alias-rollup-natural-capture.spec.ts --reporter=line` (executed from `apps/tldw-frontend`)

Artifact:

- `Docs/Product/WebUI/M1_4_Alias_Rollup_Week3_Natural_2026_02_13.json`

Capture timestamp:

- `2026-02-13T06:34:29.436Z` (UTC)

Rollup result:

| Field | Value |
|---|---|
| `total_redirects` | `0` |
| `last_event_at` | `null` |
| `top_alias_sources` | `[]` |
| `top_destinations` | `[]` |

Interpretation:

- This is the first passive natural-sample capture and it confirms no observable alias traffic in this isolated capture context.
- Controlled-sample telemetry remains the primary signal for deprecation prioritization until passive captures produce non-zero traffic.

## 8) Week-over-Week Alias Comparison (Baseline -> Controlled -> Passive Natural)

| Sample | Type | Total Redirects (raw) | Normalized Estimate | Top Alias Source | Top Destination |
|---|---|---|---|---|---|
| Week 1 (2026-02-13) | Baseline | `0` | `0` | N/A | N/A |
| Week 2 (2026-02-13) | Controlled synthetic flows | `28` | `14` (`2x` multiplier) | `/search` (`est: 3`) | `/settings` (`est: 4`) |
| Week 3 (2026-02-13) | Passive natural sample | `0` | `0` | N/A | N/A |

## 9) Deprecation Candidate Backlog Input (M2+)

Based on Week 1 baseline plus Week 2 controlled telemetry, the following alias families were prioritized for M2+ deprecation workstream planning:

1. Connectors alias family (`/connectors/*` -> `/settings`) for consolidation and retirement sequencing.
2. Long-tail admin alias family (`/admin/*` except `/admin`) -> `/admin/server`.
3. Legacy naming aliases (`/profile`, `/privileges`, `/claims-review`, `/reading`, `/audio`) pending threshold confirmation.

Threshold policy used for prioritization:

- Normalized alias usage `< 1` estimated hit/week for two consecutive weekly rollups.
- No external dependency requiring preservation.
- Canonical route smoke and recovery UX remain stable.

## 10) Next Snapshot Inputs

For the next weekly snapshot, include:

1. Alias-hit counts by source route (top 10), raw and normalized where applicable.
2. Destination distribution of alias redirects.
3. Pass/fail outcome from full smoke plus focused key-nav/wayfinding slices.
4. Deprecation candidate list based on low-use alias thresholds.
5. Route-shell unknown-path fallback verification samples (desktop + mobile).
6. Week-over-week comparison across Week 1 baseline, Week 2 controlled sample, and first natural-traffic sample.

## 11) Full-Suite Confirmation Gate (Post-change, 2026-02-13)

Capture command:

- `TLDW_SERVER_URL=http://127.0.0.1:8000 TLDW_API_KEY=THIS-IS-A-SECURE-KEY-123-FAKE-KEY bunx playwright test e2e/smoke/all-pages.spec.ts --reporter=line` (executed from `apps/tldw-frontend`)

Capture outcome:

| Metric | Result |
|---|---|
| Total tests | `165` |
| Passed | `165` |
| Failed | `0` |
| Duration | `~2.0m` |

Observed signal:

- Key navigation targets, wayfinding checks, and non-core route-boundary forced-error fixtures all passed in the same run.
- The all-pages matrix has grown from the prior 150-case baseline to 165 cases; this run supersedes the old case-count gate while preserving expected route-health coverage.
