# Implementation Plan: UX Audit v2 Cross-Cutting Themes

## Scope

This plan covers report-wide issues that affect many routes:

- Theme 1 through Theme 10 in `Docs/UX_AUDIT_REPORT_v2.md`
- Section 2 route integrity findings (404 routes, wrong-content routes, misleading redirects)
- Section 3 console warning/error reductions

## Issue Grouping Coverage

- Theme 1: `chrome.storage.local` error overlay
- Theme 2: unresolved template variables
- Theme 3: navigation links to nonexistent/wrong pages
- Theme 4: infinite re-render loops
- Theme 5: permanently loading skeletons
- Theme 6: mobile sidebar always visible
- Theme 7: icon-only controls without labels
- Theme 8: beta banner fatigue
- Theme 9: dark theme contrast concerns
- Theme 10: antd deprecations

## Pre-Implementation Validation Checklist

- Coverage alignment confirmed against `Docs/UX_AUDIT_REPORT_v2.md` Theme 1-10 and Section 2/3 findings.
- Audited route source-of-truth is fixed to the v2 manifest and route table (`ux-audit/screenshots-v2/manifest.json` plus Section 2 route list).
- Baseline metrics captured before code changes:
  - Error overlay prevalence across audited routes
  - 404/wrong-content/redirect route counts
  - Template leak occurrences (`{{...}}`)
  - Infinite render loop warning occurrences
  - Persistent skeleton occurrences
  - antd deprecation warning counts
- Test harness available for both desktop and mobile (`375x812`) route checks.
- CI can run route smoke tests and fail on regression thresholds defined in this plan.

## Stage 1: Runtime Stability Foundation
**Goal**: Eliminate extension-only runtime failures in web mode and stop route-wide overlay blocking.
**Success Criteria**:
- `chrome.storage` access is safely wrapped and falls back in all web entry points.
- Error overlays are not shown on normal page load across the audited route set.
- All new runtime guards are unit tested.
- Zero uncaught `chrome is not defined` or `chrome.storage` exceptions in web-mode route smoke runs.
**Tests**:
- Unit tests for `wxt-browser`/storage shim fallback behavior.
- Web-mode integration test that verifies no uncaught `chrome` API errors.
- Smoke navigation test across the full audited route manifest (`ux-audit/screenshots-v2/manifest.json`).
**Status**: Complete

## Stage 2: Route Integrity and Feature Gating
**Goal**: Ensure navigation never leads to 404 or unrelated pages without explicit user messaging.
**Success Criteria**:
- Sidebar navigation has zero 404 destinations.
- All routes previously identified as wrong-content now render intended content or a consistent "Coming Soon" placeholder.
- Redirect behavior is documented in a route map and treated as intentional product behavior (not fallback misrouting).
- No route in audited navigation silently redirects to unrelated settings/admin surfaces.
**Tests**:
- Route contract test matrix for all routes listed in Section 2 with expected destination and page identity assertions.
- Playwright assertions for sidebar navigation outcomes.
- Snapshot checks for placeholder pages.
**Status**: Complete
**Validation Evidence (2026-02-16)**:
- Unit test: `apps/tldw-frontend/__tests__/navigation/route-placeholder-component.test.tsx` (3 assertions; pass).
- Playwright contract: `apps/tldw-frontend/e2e/smoke/route-contract-stage2.spec.ts` (11 routes; pass).
- Artifact: `/Users/macbook-dev/Documents/GitHub/tldw_server2/Docs/Plans/artifacts/stage2_route_contract_check_2026-02-16.json`.
- Implemented placeholders for all Section 2 wrong-content routes plus additional admin hardening routes (`/admin/orgs`, `/admin/maintenance`) to eliminate silent fallback misrouting.

## Stage 3: Rendering Resilience and Loading Lifecycle
**Goal**: Remove raw template leaks, re-render loops, and permanent skeleton states.
**Success Criteria**:
- No `{{...}}` template placeholders are visible to users.
- Infinite `Maximum update depth exceeded` loops are resolved on listed routes.
- Skeleton loaders timeout after 10 seconds to explicit error/retry states.
- Retry actions re-trigger loading exactly once per user action and surface failure messaging if reattempt fails.
**Tests**:
- Component tests for fallback/template rendering.
- Hook tests for `useEffect` dependency correctness on `/content-review`, `/claims-review`, `/watchlists`, `/workspace-playground`.
- End-to-end tests validating skeleton timeout and retry states on admin + TTS/STT surfaces.
**Status**: Complete
**Validation Evidence (partial, 2026-02-16)**:
- Shared template-guard utility added and wired into Chat memory indicator, STT/TTS detail tooltips, Speech history retention hint, and Documentation source/empty-state labels.
- Shared timeout/retry flows added for admin stats and STT model discovery (used by `/stt` + `/speech` in both WebUI and extension), plus tldw TTS catalog retry handling in settings.
- Targeted test run passed (11 tests): `bun run --cwd apps/tldw-frontend vitest run --config vitest.config.ts ../packages/ui/src/utils/__tests__/template-guards.test.ts ../packages/ui/src/utils/__tests__/request-timeout.test.ts ../packages/ui/src/components/Option/Playground/__tests__/TokenProgressBar.test.tsx ../packages/ui/src/components/Option/Admin/__tests__/ServerAdminPage.media-budget.test.tsx`.
- Error-propagation hardening added for shared TTS catalog services to ensure timeout/retry UI receives thrown failures when requested (`audio-providers` and `audio-voices` now support `throwOnError`).
- New service regression coverage added: `apps/packages/ui/src/services/__tests__/audio-catalog-error-handling.test.ts` (6 tests) validates default backward-compatible fallback plus strict `throwOnError` behavior for provider and voice catalog fetches.
- Stage 3 smoke spec added and validated for route-loop + retry behavior:
  - `apps/tldw-frontend/e2e/smoke/stage3-rendering-resilience.spec.ts`
  - Run result: `8 passed` via `TLDW_WEB_AUTOSTART=false TLDW_WEB_URL=http://127.0.0.1:3000 bun run --cwd apps/tldw-frontend e2e:pw e2e/smoke/stage3-rendering-resilience.spec.ts --reporter=line`.
  - Covered in smoke: no max-depth warnings on `/content-review`, `/claims-review`, `/watchlists`, `/workspace-playground`; deterministic timeout/retry-call assertions for `/admin/server`, `/stt`, `/speech`, and `/settings/speech` (tldw catalog retry).
  - Admin case now uses a dedicated fixture profile (`seedAdminFixtureProfile`) plus route-scoped mocked admin endpoints to remove dependency on ambient backend/admin session state.

## Stage 4: Accessibility and Mobile-First Consistency
**Goal**: Fix shared accessibility and responsive issues that recur across categories.
**Success Criteria**:
- Mobile sidebar defaults to collapsed state for viewports `< 768px` and opens via explicit menu control.
- Icon-only controls include `aria-label` and tooltip coverage on audited pages.
- Dark-theme contrast targets meet WCAG AA (minimum 4.5:1 for normal text, 3:1 for large text) for audited text categories.
- Dismissible beta-banner pattern standardized and persisted in local storage.
**Tests**:
- Axe/core accessibility checks on explicit high-risk routes: `/`, `/login`, `/chat`, `/persona`, `/document-workspace`, `/workflow-editor`, `/collections`, `/data-tables`, `/watchlists`, `/evaluations`.
- Mobile viewport Playwright tests (`375x812`) for layout and tap targets.
- Contrast token validation script/test for core semantic text tokens.
**Status**: Complete
**Validation Evidence (2026-02-16)**:
- Mobile sidebar behavior is now parity-aligned across WebUI and extension via shared `WebLayout`: on `<768px` the persistent rail is hidden and chat navigation opens through a left drawer from the header toggle.
- Shared media-query hook now initializes from `window.matchMedia(...)` on first client render to avoid desktop-rail flash on mobile viewports.
- New deterministic mobile smoke coverage added and passing:
  - `apps/tldw-frontend/e2e/smoke/stage4-mobile-sidebar.spec.ts`
  - Run result: `1 passed` via `TLDW_WEB_AUTOSTART=false TLDW_WEB_URL=http://127.0.0.1:3000 bun run --cwd apps/tldw-frontend e2e:pw e2e/smoke/stage4-mobile-sidebar.spec.ts --reporter=line`.
- Icon-only controls hardening landed for Document Workspace + Workflow Editor:
  - Document Workspace left/right pane toggles now expose explicit labels (`Expand/Collapse sidebar`, `Expand/Collapse chat panel`) with test ids and matching tooltips.
  - Workflow Editor panel-switch controls now include screen-reader labels, and node config icon actions now expose explicit `aria-label`s (`Duplicate node`, `Delete node`).
- New Stage 4 accessibility smoke coverage added and passing:
  - `apps/tldw-frontend/e2e/smoke/stage4-accessibility-controls.spec.ts`
  - Run result: `2 passed` (with mobile sidebar spec) via `TLDW_WEB_AUTOSTART=false TLDW_WEB_URL=http://127.0.0.1:3000 bun run --cwd apps/tldw-frontend e2e:pw e2e/smoke/stage4-mobile-sidebar.spec.ts e2e/smoke/stage4-accessibility-controls.spec.ts --reporter=line`.
- Unit regression coverage added for workflow icon actions:
  - `apps/packages/ui/src/components/WorkflowEditor/__tests__/NodeConfigPanel.test.tsx`
  - Run result: `3 passed` via `bun run --cwd apps/tldw-frontend vitest run --config vitest.config.ts ../packages/ui/src/components/WorkflowEditor/__tests__/NodeConfigPanel.test.tsx`.
- Existing contrast gate revalidated for Stage 4 Theme 9:
  - `apps/packages/ui/src/themes/__tests__/contrast-baseline.test.ts`
  - Run result: `3 passed` via `bun run --cwd apps/tldw-frontend vitest run --config vitest.config.ts ../packages/ui/src/themes/__tests__/contrast-baseline.test.ts`.
- Theme 8 beta-badge fatigue mitigation is now standardized in shared settings navigation (web + extension parity):
  - Added persisted hide/show control in shared `SettingsLayout` (`tldw:settings:hide-beta-badges`) so beta nav badges are dismissible and remain hidden across reloads.
  - Unit coverage expanded: `apps/packages/ui/src/components/Layouts/__tests__/settings-layout-focus-order.test.tsx` now validates default badge visibility, dismissal, and persisted hidden state (`4 passed`).
  - Stage 4 smoke coverage expanded: `apps/tldw-frontend/e2e/smoke/stage4-accessibility-controls.spec.ts` now includes settings badge persistence (`2 passed` via `TLDW_WEB_AUTOSTART=false TLDW_WEB_URL=http://127.0.0.1:3000 bun run --cwd apps/tldw-frontend e2e:pw e2e/smoke/stage4-accessibility-controls.spec.ts --reporter=line`).
- Stage 4 Axe route matrix added for the high-risk set listed in this plan (`/`, `/login`, `/chat`, `/persona`, `/document-workspace`, `/workflow-editor`, `/collections`, `/data-tables`, `/watchlists`, `/evaluations`):
  - New spec: `apps/tldw-frontend/e2e/smoke/stage4-axe-high-risk-routes.spec.ts`.
  - Rule scope is deterministic and stage-aligned (landmark/region + named control semantics, with color-contrast handled by the existing contrast baseline gate).
  - Run result: `10 passed` via `TLDW_WEB_AUTOSTART=false TLDW_WEB_URL=http://127.0.0.1:3000 bun run --cwd apps/tldw-frontend e2e:pw e2e/smoke/stage4-axe-high-risk-routes.spec.ts --reporter=line`.
- Additional accessibility hardening landed in shared chat/persona surfaces (web + extension parity through shared components):
  - Hidden upload inputs now expose explicit accessibility metadata and are removed from keyboard focus in both playground and sidepanel chat forms.
  - Send split-button dropdown triggers now receive explicit menu-button labels via `buttonsRender` in both playground and sidepanel chat forms.
  - Persona route selectors now expose explicit `aria-label`s for persona, resume-session, and memory top-k controls.
- Stage 4 full smoke bundle revalidated:
  - `apps/tldw-frontend/e2e/smoke/stage4-mobile-sidebar.spec.ts`
  - `apps/tldw-frontend/e2e/smoke/stage4-accessibility-controls.spec.ts`
  - `apps/tldw-frontend/e2e/smoke/stage4-axe-high-risk-routes.spec.ts`
  - Combined run result: `13 passed` via `TLDW_WEB_AUTOSTART=false TLDW_WEB_URL=http://127.0.0.1:3000 bun run --cwd apps/tldw-frontend e2e:pw e2e/smoke/stage4-mobile-sidebar.spec.ts e2e/smoke/stage4-accessibility-controls.spec.ts e2e/smoke/stage4-axe-high-risk-routes.spec.ts --reporter=line`.

## Stage 5: UI Modernization and Release Gate
**Goal**: Reduce console noise and enforce UX quality gates before merge.
**Success Criteria**:
- antd deprecation warnings from listed APIs are removed.
- Critical route smoke suite is required in CI and blocks merge on failure.
- UX audit checklist added to PR process.
- Console warning/error budget is enforced for audited route smoke runs:
  - Zero uncaught runtime exceptions
  - Zero `Maximum update depth exceeded` warnings
  - Zero unresolved `{{...}}` placeholders in rendered UI
  - Zero listed antd deprecation warnings
**Tests**:
- Unit/component tests for migrated antd prop usage.
- CI smoke run for route load, console error threshold, and interaction sanity.
- Regression report generated against v2 issue list.
**Status**: Complete
**Validation Evidence (2026-02-16)**:
- Listed AntD deprecation APIs from Theme 10 were modernized in shared UI sources (web + extension parity through shared component usage):
  - `Drawer.width` -> `Drawer.size`
  - `Space.direction` -> `Space.orientation`
  - `Alert.message` -> `Alert.title`
  - `/chatbooks` migrated off deprecated AntD `List` usage in `apps/packages/ui/src/components/Option/Chatbooks/ChatbooksPlaygroundPage.tsx`.
- Static AST verification confirms no remaining `antd` `Drawer.width`, `Space.direction`, or `Alert.message` usages in TSX sources under `apps/packages/ui/src` and `apps/tldw-frontend`.
- New Stage 5 audited-route release gate spec added:
  - `apps/tldw-frontend/e2e/smoke/stage5-release-gate.spec.ts`
  - Budget assertions enforced per route: zero uncaught page errors, zero unexpected console/request failures, zero listed AntD deprecations, zero max-depth warnings, zero unresolved `{{...}}` placeholders.
  - Run result: `11 passed` via `TLDW_WEB_AUTOSTART=false TLDW_WEB_URL=http://127.0.0.1:3000 bun run --cwd apps/tldw-frontend e2e:pw e2e/smoke/stage5-release-gate.spec.ts --reporter=line`.
- Focused all-pages regression check for Stage 5 deprecation hotspots now passes:
  - Routes: `/settings`, `/chat/settings`, `/settings/chatbooks`, `/chatbooks`, `/flashcards`, `/admin/llamacpp`.
  - Run result: `6 passed` via `TLDW_WEB_AUTOSTART=false TLDW_WEB_URL=http://127.0.0.1:3000 bun run --cwd apps/tldw-frontend e2e:pw e2e/smoke/all-pages.spec.ts --grep "(\\/chatbooks|\\/admin\\/llamacpp|\\/settings\\/guardian|\\/flashcards|\\/settings\\))" --reporter=line`.
- CI gate wiring updated so Stage 5 audited-route suite is mandatory in PR CI:
  - `.github/workflows/frontend-ux-gates.yml` now runs `npm run e2e:smoke:stage5` in the `smoke-gate` job prior to the broad all-pages run.
  - Script added: `apps/tldw-frontend/package.json` -> `e2e:smoke:stage5`.
- UX audit PR-process checklist added:
  - `.github/pull_request_template.md` now includes an explicit Stage 5 UX gate checklist for audited-route smoke, console budget, and web/extension parity verification.
- Stage 5 continuation hardening landed for remaining Theme 10 deprecations with shared parity (web + extension):
  - Migrated `Dropdown.Button` usage to `Space.Compact + Dropdown + Button` in shared composer/prompt surfaces:
    - `apps/packages/ui/src/components/Common/PromptSearch.tsx`
    - `apps/packages/ui/src/components/Sidepanel/Chat/form.tsx`
    - `apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`
  - Migrated `Button.iconPosition` -> `iconPlacement` in `apps/packages/ui/src/components/Review/MediaReviewPage.tsx`.
  - Added shared notification compatibility patch (`message` -> `title`) for AntD v6 in:
    - `apps/packages/ui/src/utils/antd-notification-compat.ts`
    - `apps/packages/ui/src/hooks/useAntdNotification.ts`
  - Updated remaining direct static notification usage in `apps/packages/ui/src/utils/mcp-disclosure.ts` (`message` -> `title`).
- Focused all-pages verification for chat/media/review/settings routes now passes after these migrations:
  - Run result: `16 passed` via `TLDW_WEB_AUTOSTART=false TLDW_WEB_URL=http://127.0.0.1:3000 bun run --cwd apps/tldw-frontend e2e:pw e2e/smoke/all-pages.spec.ts --grep "(\\/chat\\/agent|\\/chat|\\/persona|\\/review|\\/settings\\/chat|\\/chatbooks|\\/media|\\/flashcards)" --reporter=line --workers=1`.
- Follow-up remediation completed for `ReactMarkdown` warning debt:
  - Root cause fixed by aligning shared markdown dependency resolution to v10 stack and adapting shared wrappers for v10 API (`className` removed from direct `ReactMarkdown` usage).
  - Temporary allowlist `m5-react-defaultprops-warning` removed from `apps/tldw-frontend/e2e/smoke/smoke.setup.ts`.
  - Remediation record: `Docs/Product/Completed/Plans/IMPLEMENTATION_PLAN_reactmarkdown_defaultprops_warning_remediation_2026_02_16.md`.
- Post-remediation gate revalidation:
  - Focused `/settings/chat` + `/flashcards` smoke: `4 passed`.
  - Stage 5 audited-route release gate: `11 passed`.
  - Full all-pages smoke: `165 expected`, `0 unexpected`, `0 flaky` (JSON artifact: `/tmp/all-pages-after-reactmarkdown-remediation.json`).

## Exit Criteria for Implementation Start

- All five stages have measurable pass/fail assertions accepted by frontend maintainers.
- Route matrix and baseline metrics are committed before first functional fix PR.
- CI gate design (required jobs and failure thresholds) is approved before Stage 1 execution.
