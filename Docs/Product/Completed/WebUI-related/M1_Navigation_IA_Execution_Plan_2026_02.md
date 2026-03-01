# M1 Execution Plan: Navigation and IA Consolidation

Status: Complete  
Owner: WebUI + Product  
Contributors: QA, Accessibility  
Roadmap Parent: `Docs/Product/WebUI/WebUI_UX_Strategic_Roadmap_2026_02.md`  
Date Window: February 13, 2026-March 6, 2026  
Last Updated: February 13, 2026

## Objective

Reduce navigation ambiguity and wrong-route landings by establishing one canonical route model, aligning labels across all entry points, and making route transitions/recovery states consistent.

## Scope

In scope:
- Canonical route inventory and legacy/alias deprecation map.
- Label and terminology normalization across sidebar, header shortcuts, command palette, and settings navigation.
- Wayfinding improvements (current location clarity, redirect transparency, recovery actions).
- Alias-route telemetry and UX smoke coverage for navigation regressions.

Out of scope:
- Major information architecture redesign beyond current route model.
- New feature pages unrelated to navigation discoverability.
- Backend API changes except optional telemetry endpoint wiring.

## Milestones

| Milestone | Window | Focus | Owner | Status | Exit Criteria |
|---|---|---|---|---|---|
| M1.1 | Feb 13-Feb 17, 2026 | Canonical route inventory + alias matrix | WebUI | Complete | Canonical map and deprecation states documented and reviewed |
| M1.2 | Feb 18-Feb 24, 2026 | Label normalization across nav surfaces | WebUI + Product | Complete (Engineering) | Destination labels consistent across major entry points |
| M1.3 | Feb 25-Mar 2, 2026 | Wayfinding + recovery UX alignment | WebUI | Complete | Users can identify location and recover from off-path states |
| M1.4 | Mar 3-Mar 6, 2026 | Telemetry + verification + cutover readiness | WebUI + QA | Complete | Alias usage measurable and smoke checks passing |

## Baseline Route Alias Inventory (Current)

Known redirect aliases in `apps/tldw-frontend/pages`:

| Legacy Route | Canonical Route |
|---|---|
| `/search` | `/knowledge` |
| `/config` | `/settings` |
| `/profile` | `/settings` |
| `/privileges` | `/settings` |
| `/audio` | `/speech` |
| `/reading` | `/collections` |
| `/claims-review` | `/content-review` |
| `/media/[id]/view` | `/media` |
| `/connectors`, `/connectors/browse`, `/connectors/jobs`, `/connectors/sources` | `/settings` |
| `/admin`, `/admin/orgs`, `/admin/data-ops`, `/admin/watchlists-items`, `/admin/watchlists-runs`, `/admin/maintenance` | `/admin/server` |
| `/prompt-studio` | `/prompts?tab=studio` |

## M1.1: Canonical Route Inventory + Alias Matrix

Primary files:
- `apps/packages/ui/src/routes/route-registry.tsx`
- `apps/packages/ui/src/routes/route-paths.ts`
- `apps/tldw-frontend/pages/**/*.tsx` (redirect pages using `RouteRedirect`)
- `apps/tldw-frontend/components/navigation/RouteRedirect.tsx`
- `apps/tldw-frontend/e2e/smoke/page-inventory.ts`

Deliverables:
- Canonical route registry table (route, category, owner, status: canonical/beta/legacy).
- Deprecation matrix for alias pages (keep, sunset date, replacement).
- Naming policy for path slugs and route labels.

Tracking checklist:
- [x] Export current canonical routes from `route-registry.tsx` (captured in `Docs/Product/Completed/WebUI-related/M1_1_Canonical_Route_Inventory_2026_02.md`).
- [x] Enumerate all alias pages and redirect targets from `pages/` (captured in `Docs/Product/Completed/WebUI-related/M1_1_Canonical_Route_Inventory_2026_02.md`).
- [x] Confirm canonical-vs-legacy treatment for each route in `page-inventory.ts` (documented in `Docs/Product/Completed/WebUI-related/M1_1_Canonical_Route_Inventory_2026_02.md`).
- [x] Publish route inventory doc under `Docs/Product/WebUI/` (`Docs/Product/Completed/WebUI-related/M1_1_Canonical_Route_Inventory_2026_02.md`).
- [x] Add changelog section to track route migrations (`Docs/Product/Completed/WebUI-related/M1_1_Canonical_Route_Inventory_2026_02.md`).

Acceptance criteria:
- Every user-facing route has one canonical destination.
- Every alias route is either documented with a deprecation timeline or removed.
- No route in smoke inventory points to an undefined destination.

## M1.2: Label Normalization Across Navigation Surfaces

Primary files:
- `apps/packages/ui/src/components/Common/ChatSidebar.tsx`
- `apps/packages/ui/src/components/Common/ChatSidebar/shortcut-actions.ts`
- `apps/packages/ui/src/components/Layouts/header-shortcut-items.ts`
- `apps/packages/ui/src/components/Common/CommandPalette.tsx`
- `apps/packages/ui/src/components/Layouts/settings-nav.ts`
- `apps/packages/ui/src/i18n/lang/en.ts` (and localization follow-up set)

Deliverables:
- One terminology map (Route -> Canonical label -> Alias labels disallowed).
- Harmonized labels for shared destinations (examples: Knowledge QA, Media, Notes, Settings).
- Translation token cleanup plan for renamed labels.

Tracking checklist:
- [x] Build cross-surface label matrix for sidebar/header/command/settings (`Docs/Product/Completed/WebUI-related/M1_2_Navigation_Terminology_Triage_2026_02.md`).
- [x] Resolve conflicting labels for identical routes.
- [x] Standardize one preferred term per destination and update components.
- [x] Validate keyboard shortcut hints match actual behavior (`apps/packages/ui/src/components/Common/__tests__/CommandPalette.shortcuts.test.tsx`).
- [x] Capture before/after screenshots for unchanged semantics with clearer labeling (`Docs/Product/WebUI/evidence/m1_2_label_alignment_2026_02_13/`).

Progress update (February 12, 2026):
- Implemented a first pass in tracked files: command palette entries for Knowledge QA and Prompts, Health label normalization, Quick Ingest capitalization cleanup, Chat Dictionaries casing fallback, and explicit settings labels for Research Studio and Model Playground.

Progress update (February 13, 2026):
- Completed terminology closeout in route/header/locale mappings, including Research Studio vs Model Playground label-token alignment and Multi-Item Review route label normalization.
- Added command palette shortcut-hint alignment so pills derive from actual configured/bound shortcuts.
- Verified closeout via focused smoke (`10 passed`, key-nav + wayfinding), full smoke (`150 passed`), and command palette shortcut unit test (`1 passed`).
- Captured post-change desktop/mobile evidence screenshots under `Docs/Product/WebUI/evidence/m1_2_label_alignment_2026_02_13/`.
- Product sign-off recorded for canonical vocabulary in `Docs/Product/Completed/WebUI-related/M1_2_Navigation_Terminology_Triage_2026_02.md`.

Acceptance criteria:
- Same destination has same primary label across all major nav entry points.
- No ambiguous synonyms remain in default English labels for core routes.
- Command palette results rank canonical names before aliases.

## M1.3: Wayfinding + Recovery UX Alignment

Primary files:
- `apps/packages/ui/src/components/Layouts/SettingsOptionLayout.tsx`
- `apps/packages/ui/src/components/Common/ChatSidebar.tsx`
- `apps/packages/ui/src/components/Layouts/Header.tsx`
- `apps/packages/ui/src/routes/app-route.tsx`
- `apps/tldw-frontend/components/navigation/RouteRedirect.tsx`
- `apps/tldw-frontend/pages/404.tsx`
- `apps/packages/ui/src/components/Layouts/Layout.tsx` (shell-level consistency)
- `Docs/Product/Completed/WebUI-related/M1_3_Wayfinding_Manual_QA_Script_2026_02.md`

Deliverables:
- Clear "you are here" affordances in settings and key workspace sections.
- Redirect and 404 recovery patterns aligned to the same design language.
- Back/close behavior rules for settings and redirected pages.

Tracking checklist:
- [x] Verify active-route indication in settings nav and app shell (`apps/packages/ui/src/components/Layouts/SettingsOptionLayout.tsx` with nested-route matching + section indicator).
- [x] Ensure redirect interstitial copy is action-oriented and consistent (`apps/tldw-frontend/components/navigation/RouteRedirect.tsx`).
- [x] Ensure 404 recovery provides primary and secondary pathways (`apps/tldw-frontend/pages/404.tsx`).
- [x] Add shell-level unknown-route recovery fallback to avoid header-only blank states (`apps/packages/ui/src/routes/app-route.tsx`, `apps/tldw-frontend/extension/routes/app-route.tsx`).
- [x] Validate focus order and keyboard operation for nav/redirect/recovery controls (`apps/packages/ui/src/components/Layouts/__tests__/settings-layout-focus-order.test.tsx`, `apps/tldw-frontend/__tests__/navigation/route-redirect-component.test.tsx`, `apps/tldw-frontend/__tests__/navigation/not-found-page.test.tsx`).
- [x] Add route-wayfinding scenarios to smoke and manual QA scripts (`apps/tldw-frontend/e2e/smoke/all-pages.spec.ts`, `Docs/Product/Completed/WebUI-related/M1_3_Wayfinding_Manual_QA_Script_2026_02.md`).

Progress update (February 13, 2026):
- Added explicit active-route matching for nested settings paths, visible current-section indicator, and stronger active-state affordances in settings navigation.
- Aligned redirect and 404 recovery copy/actions around consistent "route moved/not found -> continue with Chat/Settings/primary target" language.
- Normalized alias redirect pages to use a single shared redirect language pattern through `RouteRedirect` defaults.
- Added shell-level catch-all recovery panel to replace unmatched-route blank content with actionable fallback controls.
- Added chat-sidebar shortcut active-route affordances (including settings and nested-route handling) for faster orientation outside settings pages.
- Added keyboard and focus-order tests for settings nav, route redirect controls, and 404 recovery actions.
- Added dedicated wayfinding smoke scenarios (active settings location, alias redirect destination check, 404 control order) and a manual QA script for evidence collection; scenarios are currently skip-guarded when runtime route parity is unavailable.
- Resolved direct settings-route parity by fixing a cyclic import initialization hazard (`createSettingsRoute` now exported as a hoisted function), restoring `/settings*` content rendering in focused smoke verification.

Acceptance criteria:
- Users can identify current location within one interaction on key routes.
- Redirect pages expose destination and immediate action controls.
- 404 state provides at least one context-relevant recovery path.

## M1.4: Telemetry + Verification + Cutover Readiness

Primary files:
- `apps/packages/ui/src/utils/` (new route telemetry helper, parallel to media telemetry pattern)
- `apps/tldw-frontend/e2e/smoke/all-pages.spec.ts`
- `apps/tldw-frontend/e2e/smoke/page-inventory.ts`
- `apps/tldw-frontend/__tests__/navigation/route-redirect.test.ts`
- `apps/packages/ui/src/components/Layouts/__tests__/settings-nav.guardian.test.ts` (pattern reference)

Deliverables:
- Alias route hit telemetry (source path, destination, timestamp, optional query/hash carryover).
- Weekly alias-usage report for deprecation decisions.
- Navigation regression checks in smoke suite.

Tracking checklist:
- [x] Implement local route-alias telemetry store/helper (`apps/packages/ui/src/utils/route-alias-telemetry.ts`).
- [x] Instrument `RouteRedirect` alias transitions (`apps/tldw-frontend/components/navigation/RouteRedirect.tsx`).
- [x] Add tests for telemetry recording and route normalization logic (`apps/packages/ui/src/utils/__tests__/route-alias-telemetry.test.ts`, `apps/tldw-frontend/__tests__/navigation/route-redirect-component.test.tsx`).
- [x] Add weekly rollup helper for alias-source/destination trends (`apps/packages/ui/src/utils/route-alias-telemetry.ts`, `apps/packages/ui/src/utils/__tests__/route-alias-telemetry.test.ts`).
- [x] Expand smoke checks to assert key nav targets are reachable (`apps/tldw-frontend/e2e/smoke/all-pages.spec.ts`).
- [x] Add runtime-overlay regression guard to smoke for syntax/runtime crash signatures (`apps/tldw-frontend/e2e/smoke/all-pages.spec.ts`).
- [x] Capture first weekly alias telemetry rollup (`getRouteAliasTelemetryRollup({ topN: 10 })`) and append to M1.4 snapshot (`Docs/Product/Completed/WebUI-related/M1_4_Route_Health_Snapshot_2026_02_12.md`).
- [x] Capture controlled non-zero Week 2 alias telemetry sample via Playwright and persist JSON artifact (`apps/tldw-frontend/e2e/smoke/alias-rollup-capture.spec.ts`, `Docs/Product/WebUI/M1_4_Alias_Rollup_Week2_Controlled_2026_02_13.json`).
- [x] Publish weekly route health snapshot (`Docs/Product/Completed/WebUI-related/M1_4_Route_Health_Snapshot_2026_02_12.md`).

Progress update (February 13, 2026):
- Added M2-prep route-level boundary contract and applied shared route boundaries across key nav targets (`chat`, `media`, `knowledge`, `notes`, `prompts`, `settings`), then reran focused key-nav + wayfinding smoke (`10 passed`).
- Updated smoke inventory `/chat` readiness selector from `chat-header` to `chat-input` to match current shell implementation.
- Reran full smoke suite after wayfinding and selector alignment: `150 passed`.
- Added runtime-overlay assertions in smoke to fail on Next runtime crash signatures (`Runtime Error`, `Runtime SyntaxError`, `Invalid or unexpected token`, React-child object runtime error), then revalidated focused (`10/10`) and full (`150/150`) suites.
- Captured first weekly alias rollup (`2026-02-13T03:29:47.844Z`) using `getRouteAliasTelemetryRollup({ topN: 10 })`; baseline currently reports `0` redirects.
- Added controlled alias-rollup capture smoke spec and executed it (`bunx playwright test e2e/smoke/alias-rollup-capture.spec.ts --reporter=line`): non-zero sample captured with raw `28` redirects and normalized estimate `14` (`2x` dev duplicate multiplier), persisted to `Docs/Product/WebUI/M1_4_Alias_Rollup_Week2_Controlled_2026_02_13.json`.
- Revalidated focused key-nav + wayfinding smoke after controlled capture setup: `10 passed` (11.3s).
- Revalidated full smoke after controlled capture setup: `150 passed` (1.6m).

Acceptance criteria:
- Alias usage is measurable week-over-week.
- No critical navigation regressions in smoke results before M1 close.
- Deprecation candidates identified with data-backed thresholds.

## Task-to-File Delivery Matrix

| Workstream | Key Files | Output |
|---|---|---|
| Canonical route map | `apps/packages/ui/src/routes/route-registry.tsx`, `apps/tldw-frontend/e2e/smoke/page-inventory.ts` | Single canonical map and coverage parity |
| Alias route handling | `apps/tldw-frontend/pages/**/*.tsx`, `apps/tldw-frontend/components/navigation/RouteRedirect.tsx` | Explicit alias lifecycle + instrumented redirects |
| Label harmonization | `apps/packages/ui/src/components/Common/ChatSidebar.tsx`, `apps/packages/ui/src/components/Layouts/header-shortcut-items.ts`, `apps/packages/ui/src/components/Common/CommandPalette.tsx`, `apps/packages/ui/src/components/Layouts/settings-nav.ts` | Unified navigation terminology |
| Wayfinding | `apps/packages/ui/src/components/Layouts/SettingsOptionLayout.tsx`, `apps/packages/ui/src/components/Common/ChatSidebar.tsx`, `apps/packages/ui/src/routes/app-route.tsx`, `apps/tldw-frontend/pages/404.tsx` | Consistent "location + recovery" behavior |
| Validation | `apps/tldw-frontend/e2e/smoke/all-pages.spec.ts`, `apps/tldw-frontend/__tests__/navigation/route-redirect.test.ts` | Passing nav regression checks |

## Metrics and Targets

| Metric | Baseline | M1 Target |
|---|---|---|
| Alias-route hit share | Unknown | Baseline established by end of M1.4 |
| Wrong-route landing observations in UX smoke | Present | Downward trend week over week |
| Label mismatch count across key nav surfaces | High | Zero critical mismatches for core routes |
| Navigation-related runtime errors | Low but non-zero risk | Zero critical regressions in smoke runs |

## Weekly Tracking Log

| Week | Date | Milestone | Planned Outcome | Actual Outcome | Status |
|---|---|---|---|---|---|
| Week 1 | Feb 13, 2026 | M1.1 | Canonical route/alias inventory draft | Canonical route inventory and alias matrix published | Complete |
| Week 2 | Feb 20, 2026 | M1.2 | Label matrix and first normalization pass | Label triage published, terminology normalization completed, and verification/evidence captured | Complete (Engineering) |
| Week 3 | Feb 27, 2026 | M1.3 | Wayfinding and recovery pattern alignment | Active-route clarity + redirect/404 copy alignment + keyboard/focus validation + shell-level unknown-route fallback + sidebar active-route affordances added | Complete |
| Week 4 | Mar 6, 2026 | M1.4 | Telemetry + verification + closeout report | Telemetry helper + redirect instrumentation + runtime-overlay smoke guard landed; focused key-nav/wayfinding reruns passing (10/10), full smoke reruns passing (150/150), controlled Week 2 alias capture recorded (raw 28, normalized 14), and deprecation candidates prioritized for M2+ backlog | Complete |

## M1.4 Deprecation Candidates (Prioritized for M2+)

Prioritization inputs:
- Alias inventory: `Docs/Product/Completed/WebUI-related/M1_1_Canonical_Route_Inventory_2026_02.md`
- Alias rollups: `Docs/Product/Completed/WebUI-related/M1_4_Route_Health_Snapshot_2026_02_12.md`
- Consolidation leverage (families that can be reduced together)

Threshold policy for safe alias retirement:
1. Alias/family normalized usage `< 1` estimated hit/week for two consecutive weekly rollups.
2. No documented external dependency (docs/bookmarks/shared links) requiring preservation.
3. Canonical route has stable smoke coverage and recovery UX.

Backlog priority:

| Priority | Alias Candidate | Canonical Target | Rationale | Proposed M2+ Action |
|---|---|---|---|---|
| P1 | `/connectors/browse`, `/connectors/jobs`, `/connectors/sources` | `/settings` | Redundant sub-route aliases to same destination; high simplification payoff | Consolidate to single `/connectors` alias first, then evaluate full family retirement |
| P1 | `/admin/orgs`, `/admin/data-ops`, `/admin/watchlists-items`, `/admin/watchlists-runs`, `/admin/maintenance` | `/admin/server` | Redundant admin family aliases to one canonical page | Keep `/admin` alias, retire long-tail admin family when threshold met |
| P2 | `/profile`, `/privileges` | `/settings` | Legacy naming drift with overlapping settings intent | Soft deprecate with release notes and in-app redirect notice |
| P2 | `/claims-review` | `/content-review` | Terminology drift after workflow consolidation | Keep during one release cycle, then retire when usage threshold is met |
| P3 | `/reading` | `/collections` | Legacy IA term; canonical workspace established | Retire after two low-usage weekly rollups |
| P3 | `/audio` | `/speech` | Legacy naming retained for compatibility | Retire after two low-usage weekly rollups |
| P3 | `/media/:id/view` | `/media` | Parameterized legacy deep-link shim | Keep until deep-link usage is below threshold, then replace with canonical query-based deep link |

## Dependencies and Risks

Dependencies:
- Product decision on preferred route names/terminology.
- QA availability for expanded smoke coverage and evidence capture.
- Localization support for post-normalization string updates.

Risks:
- Label changes can create temporary user confusion without release notes.
- Alias removal can break old links/bookmarks if no measured rollout.
- Cross-surface updates can drift without one owner per nav system.

Mitigations:
- Ship label changes with small release notes in settings/help.
- Keep alias redirects until telemetry proves safe removal threshold.
- Assign single DRI for navigation taxonomy and weekly review.

## Done Criteria for M1 Close

- [x] M1.1-M1.4 exit criteria all met.
- [x] Route/alias inventory approved and linked from strategic roadmap.
- [x] Core navigation smoke checks passing on latest mainline.
- [x] Deprecation candidates prioritized for M2+ backlog.
