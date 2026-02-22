# Implementation Plan: UX Audit v2 Interaction Tests

## Scope

Interaction audit findings and smoke behaviors  
Issue IDs: `INT-1` through `INT-6`

## Issue Grouping Coverage

- `INT-1`: Chat input works but template variable leak still visible
- `INT-2`: Search typing works (positive)
- `INT-3`: Search results/no-results behavior works (positive)
- `INT-4`: Command palette behavior works (positive)
- `INT-5`: Theme toggle not found on home
- `INT-6`: Settings sidebar navigation works (positive)

## Stage 1: Close Interaction Defects
**Goal**: Resolve interaction-level blockers reported by exploratory tests.
**Success Criteria**:
- Chat interaction path no longer exposes `{{percentage}}`.
- Theme toggle is discoverable on home (or intentionally relocated with clear path).
- No regressions to existing successful interactions.
**Tests**:
- Targeted Playwright tests for chat input, theme toggle discovery, and home controls.
- Snapshot comparison for chat empty/composer states.
**Status**: Complete

## Stage 2: Promote Positives into Regression Suite
**Goal**: Convert successful manual interactions into permanent automated coverage.
**Success Criteria**:
- Existing good behaviors (search typing/results, command palette, settings nav) are encoded as stable smoke tests.
- Keyboard shortcuts and focus behavior are verified.
- Test data/setup for interaction suite is deterministic.
**Tests**:
- E2E tests for `Cmd+K`, search query/no-results, and settings navigation.
- Accessibility checks for keyboard-only command palette execution.
**Status**: Complete

## Stage 3: Interaction Gate for Releases
**Goal**: Use interaction tests as a release quality gate.
**Success Criteria**:
- Interaction suite runs in CI on pull requests touching web UI.
- Failures provide route/action-level diagnostics.
- Baseline pass criteria are documented in frontend contribution guidance.
**Tests**:
- CI workflow validation with failing/passing interaction scenarios.
- Flake-rate tracking over repeated runs.
**Status**: Complete

## Progress Notes (2026-02-17)
- Stage 1 defect closure completed for `INT-1` and `INT-5`:
  - Added explicit, always-visible theme toggle control to the shared top header so it is discoverable from home and other shell pages:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Layouts/ChatHeader.tsx`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Layouts/Header.tsx`
  - Added header regression coverage for theme toggle affordance and callback wiring:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Layouts/__tests__/ChatHeader.test.tsx`
  - Added Stage 1 interaction smoke checks for:
    - unresolved template placeholder absence on `/chat` (`INT-1`)
    - explicit theme toggle visibility + functional class toggle on `/` (`INT-5`)
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend/e2e/smoke/stage6-interaction-stage1.spec.ts`
  - Added `/chat` to release-gate critical route coverage so unresolved-template checks include chat:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend/e2e/smoke/stage5-release-gate.spec.ts`
- Validation runs:
  - `cd apps/packages/ui && bunx vitest run src/components/Layouts/__tests__/ChatHeader.test.tsx src/components/Option/Playground/__tests__/TokenProgressBar.test.tsx`
  - Result: `2 passed` test files, `7 passed` tests.
  - `cd apps/tldw-frontend && bunx playwright test e2e/smoke/stage6-interaction-stage1.spec.ts --reporter=line`
  - Result: `2 passed` tests.
- Stage 2 positive-regression promotion completed for `INT-2`, `INT-3`, `INT-4`, and `INT-6`:
  - Added deterministic interaction smoke suite:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend/e2e/smoke/stage6-interaction-stage2.spec.ts`
  - Coverage includes:
    - `/search` -> `/knowledge` typing flow with deterministic no-results AI answer (`INT-2`, `INT-3`).
    - keyboard-only command palette open/focus/execute via `Cmd/Ctrl+K` (`INT-4`).
    - settings sidebar click navigation with active-state assertion (`INT-6`).
- Stage 2 validation run:
  - `cd apps/tldw-frontend && bunx playwright test e2e/smoke/stage6-interaction-stage2.spec.ts --reporter=line`
  - Result: `3 passed` tests.
- Stage 2 suite expansion:
  - added mobile chat composer control parity + touch-target assertions on `/chat`:
    - `apps/tldw-frontend/e2e/smoke/stage6-interaction-stage2.spec.ts`
    - validates `Attach image`, `Send message`, and `Open send options` visibility plus `>= 44px` target size on mobile viewport.
  - supporting control sizing hardening landed in:
    - `apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`
- Stage 2 validation rerun after expansion:
  - `cd apps/tldw-frontend && bunx playwright test e2e/smoke/stage6-interaction-stage2.spec.ts --reporter=line`
  - Result: `4 passed` tests.
- Stage 3 release-gate integration completed:
  - Added Stage 6 interaction gate command scripts in:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend/package.json`
      - `e2e:smoke:interaction:stage1`
      - `e2e:smoke:interaction:stage2`
      - `e2e:smoke:interaction`
  - Wired CI smoke gate to run Stage 6 interaction suite:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/.github/workflows/frontend-ux-gates.yml`
      - added `Run Stage 6 interaction regression gate` step (`npm run e2e:smoke:interaction`)
  - Hardened release-gate navigation behavior for transient runtime transport failures:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend/e2e/smoke/stage5-release-gate.spec.ts`
  - Documented baseline UX gate pass criteria and interaction coverage in:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend/README.md`
- Stage 3 validation run:
  - `cd apps/tldw-frontend && bunx playwright test e2e/smoke/stage6-interaction-stage1.spec.ts e2e/smoke/stage6-interaction-stage2.spec.ts --reporter=line`
  - Result: `5 passed` tests.
- Stage 3 gate rerun after Stage 2 suite expansion:
  - `cd apps/tldw-frontend && bunx playwright test e2e/smoke/stage6-interaction-stage1.spec.ts e2e/smoke/stage6-interaction-stage2.spec.ts --reporter=line`
  - Result: `6 passed` tests.
- Stage 3 flake-rate tracking run:
  - `cd apps/tldw-frontend && bunx playwright test e2e/smoke/stage6-interaction-stage1.spec.ts e2e/smoke/stage6-interaction-stage2.spec.ts --repeat-each=3 --reporter=line`
  - Result: `15 passed` tests, `0` flakes observed in this run.
- Stage 3 strict-gate hardening follow-up:
  - Root cause for prior Stage 5 skip on `/chat/settings` isolated to a Turbopack route compile stall in dev runtime.
  - Replaced `/chat/settings` page-module alias with server-level redirect in:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend/next.config.mjs`
      - `source: '/chat/settings' -> destination: '/settings/chat'`
  - Tightened Stage 5 release gate to fail on unavailable/4xx+ critical routes (no skip fallback) and aligned expected path for `/chat/settings`:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend/e2e/smoke/stage5-release-gate.spec.ts`
  - Direct route probe validation:
    - `curl --max-time 20 http://localhost:8080/chat/settings` -> `307` (immediate redirect)
    - `curl --max-time 20 http://localhost:8080/settings/chat` -> `200`
  - Strict gate validation:
    - `cd apps/tldw-frontend && bunx playwright test e2e/smoke/stage5-release-gate.spec.ts -g "Chat Settings" --reporter=line`
    - Result: `1 passed` (`6.7s`).
    - `cd apps/tldw-frontend && bunx playwright test e2e/smoke/stage5-release-gate.spec.ts --reporter=line`
    - Result: `12 passed` (`21.4s`), `0` skipped.
  - Regression confirmation:
    - `cd apps/tldw-frontend && bunx playwright test e2e/smoke/stage6-interaction-stage1.spec.ts e2e/smoke/stage6-interaction-stage2.spec.ts --reporter=line`
    - Result: `6 passed` (`10.4s`).
