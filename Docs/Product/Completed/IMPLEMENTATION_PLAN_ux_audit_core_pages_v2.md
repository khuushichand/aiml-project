# Implementation Plan: UX Audit v2 Core Pages

## Scope

Pages: Home, Login, Setup, Onboarding  
Issue IDs: `CORE-1` through `CORE-7`

## Issue Grouping Coverage

- `CORE-1`: Demo banner mobile layout break
- `CORE-2`: Sidebar visible on mobile
- `CORE-3`: Low-contrast "Skip for now"
- `CORE-4`: Validation text contrast risk
- `CORE-5`: Ambiguous status badges ("Core: waiting", "RAG: waiting")
- `CORE-6`: Floating avatar overlap on mobile
- `CORE-7`: Duplicate content across three routes

## Stage 1: Core Route Baseline and Acceptance Criteria
**Goal**: Capture current behavior and define measurable UX acceptance for core routes.
**Success Criteria**:
- Core route acceptance checklist exists for desktop/mobile.
- Overlap/contrast/tap-target constraints are documented per route.
- Route-differentiation expectation is defined for home/setup/onboarding.
**Tests**:
- Baseline Playwright screenshots for 1440x900 and 375x812.
- Route-level smoke assertions for successful render.
**Status**: Complete

## Stage 2: Mobile Layout and Structural Fixes
**Goal**: Resolve core mobile layout blockers.
**Success Criteria**:
- Demo banner wraps naturally and remains readable on mobile.
- Sidebar behavior is responsive and non-obstructive in mobile viewport.
- Floating avatar no longer overlaps helper/validation text.
**Tests**:
- Mobile visual regression for home/login.
- Layout assertions for minimum readable content width.
**Status**: Complete

## Stage 3: Accessibility and Microcopy Clarity
**Goal**: Improve clarity and contrast for core onboarding actions and status indicators.
**Success Criteria**:
- "Skip for now" link passes contrast and affordance expectations.
- Validation/status text colors meet WCAG AA in dark theme.
- Login status badges use user-facing wording with explicit state meaning.
**Tests**:
- Automated contrast checks for affected token pairs.
- Unit tests for revised status badge mapping/copy.
**Status**: Complete

## Stage 4: Route Identity and Regression Hardening
**Goal**: Ensure home/setup/onboarding-test present distinct, intentional content.
**Success Criteria**:
- Each route has unique heading/objective and non-duplicated primary CTA.
- Navigation between these routes preserves expected setup state.
- Regression tests prevent accidental route-content duplication.
**Tests**:
- Integration tests comparing route-specific heading/content markers.
- End-to-end first-run flow test from home -> setup -> onboarding.
**Status**: Complete

## Progress Notes (2026-02-17)
- Stage 1 baseline accepted from UX audit v2 capture set (`ux-audit/screenshots-v2/home_mobile.png`, `ux-audit/screenshots-v2/login_mobile.png`, `ux-audit/screenshots-v2/setup_mobile.png`) and route-intent expectations documented in this plan.
- Stage 2 mobile layout fixes completed (`CORE-1`, `CORE-2`, `CORE-6`):
  - Added nested layout support for `hideSidebar` overrides so route-level onboarding shells can fully suppress mobile left rail.
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Layouts/Layout.tsx`
  - Applied `hideSidebar` on first-run core routes to prevent mobile sidebar width loss and overlap:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/routes/option-index.tsx`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/routes/option-setup.tsx`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/routes/option-onboarding-test.tsx`
  - Updated onboarding demo banner for mobile stacking/readability (button moves to full-width row on small viewports):
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/Onboarding/OnboardingConnectForm.tsx`
- Stage 3 accessibility/microcopy fixes completed (`CORE-3`, `CORE-4`, `CORE-5`):
  - Improved skip-link affordance/contrast (underline + clearer muted text treatment):
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/Onboarding/OnboardingConnectForm.tsx`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/Onboarding/OnboardingWizard.tsx`
  - Reworked success validation copy styling away from low-contrast green body text:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/Onboarding/OnboardingConnectForm.tsx`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/Onboarding/OnboardingWizard.tsx`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/Settings/tldw.tsx`
  - Clarified unknown status badge wording from “waiting” to explicit “not checked yet”:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/Settings/tldw-connection-status.ts`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/Settings/tldw.tsx`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/assets/locale/en/settings.json`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/public/_locales/en/settings.json`
  - Added unit coverage for revised status mapping copy:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/Settings/__tests__/tldw-connection-status.test.ts`
- Stage 4 route identity remediation completed (`CORE-7`):
  - Added distinct route-intent headings/objectives for first-run home, setup, and onboarding-test surfaces:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/routes/option-index.tsx`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/routes/option-setup.tsx`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/routes/option-onboarding-test.tsx`
  - Routed `/onboarding-test` to dedicated route components in both UI and extension registries:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/routes/route-registry.tsx`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend/extension/routes/route-registry.tsx`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend/pages/onboarding-test.tsx`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend/extension/routes/option-onboarding-test.tsx`
- Added core route identity regression coverage:
  - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/routes/__tests__/core-route-identity.test.tsx`
- Extended route identity regression to enforce core-route `hideSidebar` behavior.
- Validation run:
  - `cd apps/packages/ui && bunx vitest run src/routes/__tests__/core-route-identity.test.tsx src/routes/__tests__/option-media-route-guards.test.tsx`
  - Result: `2 passed` test files, `3 passed` tests.
- Validation run:
  - `cd apps/packages/ui && bunx vitest run src/routes/__tests__/core-route-identity.test.tsx src/routes/__tests__/option-media-route-guards.test.tsx src/components/Option/Settings/__tests__/tldw-connection-status.test.ts`
  - Result: `3 passed` test files, `5 passed` tests.
- Validation run:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/Settings/__tests__/ChatSettings.test.tsx src/components/Option/Settings/__tests__/GuardianSettings.test.tsx src/components/Option/Settings/__tests__/rag.test.tsx src/components/Option/Settings/__tests__/tldw-connection-status.test.ts`
  - Result: `4 passed` test files, `17 passed` tests.
