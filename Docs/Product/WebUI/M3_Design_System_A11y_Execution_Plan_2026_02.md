# M3 Execution Plan: Design System and Accessibility Baseline

Status: In Progress  
Owner: WebUI + Accessibility  
Date: February 13, 2026  
Roadmap Link: `Docs/Product/WebUI/WebUI_UX_Strategic_Roadmap_2026_02.md`

## 1) Objective

Establish enforceable design-token and accessibility baselines for core WebUI journeys so future UX work can ship behind measurable WCAG 2.2 AA checks instead of ad-hoc visual QA.

## 2) Milestones

| Milestone | Window | Focus | Status | Exit Criteria |
|---|---|---|---|---|
| M3.1 | Feb 13-Feb 20, 2026 | Token inventory + contrast guardrails | Complete | Core token map published, automated contrast guardrail test passing |
| M3.2 | Feb 20-Mar 3, 2026 | Keyboard/focus path normalization | Complete | Core workflows pass keyboard/focus QA script and targeted tests |
| M3.3 | Mar 3-Mar 10, 2026 | Component baseline and release gates | In Progress | Button/input/alert/empty-state baseline published and referenced in release checklist |

## 3) Deliverables

1. Token baseline doc with WCAG mapping and theme contrast guardrails.
2. Core-flow accessibility QA script for keyboard navigation and focus-visible checks.
3. Focus-visible normalization in app shell controls.
4. Roadmap and release-checklist linkage for ongoing governance.

## 4) Current Progress (February 13, 2026)

- Added reusable contrast utility and WCAG helpers:
  - `apps/packages/ui/src/themes/contrast.ts`
- Added enforceable core theme contrast baseline tests:
  - `apps/packages/ui/src/themes/__tests__/contrast-baseline.test.ts`
- Raised default light focus token contrast for visible keyboard focus rings:
  - `apps/packages/ui/src/themes/presets.ts`
  - `apps/packages/ui/src/assets/tailwind-shared.css`
- Normalized focus-visible classes in high-frequency shell controls:
  - `apps/packages/ui/src/components/Layouts/ChatHeader.tsx`
  - `apps/packages/ui/src/components/Common/ChatSidebar.tsx`
- Captured full M3.2 desktop/mobile route-matrix evidence set:
  - `Docs/Product/WebUI/evidence/m3_2_a11y_focus_2026_02_13/`
- Added focus-visible regression assertions for high-frequency non-shell modal controls:
  - `apps/packages/ui/src/components/Common/CommandPalette.tsx`
  - `apps/packages/ui/src/components/Common/__tests__/CommandPalette.shortcuts.test.tsx`
  - `apps/packages/ui/src/components/Common/__tests__/KeyboardShortcutsModal.focus.test.tsx`
- Finalized M3.3/M4 non-core theme hard-gate cut-line memo:
  - `Docs/Product/WebUI/M3_3_NonCore_Theme_Contrast_HardGate_Decision_2026_02.md`

## 5) Validation Evidence

- `bunx vitest run ../packages/ui/src/themes/__tests__/contrast-baseline.test.ts ../packages/ui/src/components/Layouts/__tests__/ChatHeader.test.tsx ../packages/ui/src/components/Common/ChatSidebar/__tests__/shortcut-active.test.ts`
  - Outcome: `11 passed`
- `bunx vitest run ../packages/ui/src/components/Common/__tests__/CommandPalette.shortcuts.test.tsx ../packages/ui/src/components/Common/__tests__/KeyboardShortcutsModal.focus.test.tsx ../packages/ui/src/components/Layouts/__tests__/ChatHeader.test.tsx ../packages/ui/src/themes/__tests__/contrast-baseline.test.ts`
  - Outcome: `9 passed`
- `TLDW_E2E_SERVER_URL=127.0.0.1:8000 TLDW_E2E_API_KEY=THIS-IS-A-SECURE-KEY-123-FAKE-KEY bunx playwright test e2e/smoke/all-pages.spec.ts --grep "Key Navigation|Wayfinding|Route Error Boundaries" --reporter=line`
  - Outcome: `25 passed` (post-M3 modal-focus regression gate)
- `TLDW_SERVER_URL=http://127.0.0.1:8000 TLDW_API_KEY=THIS-IS-A-SECURE-KEY-123-FAKE-KEY bunx playwright test e2e/smoke/m3-2-a11y-focus-evidence.spec.ts --reporter=line`
  - Outcome: `2 passed` (desktop + mobile route-matrix capture)

## 6) Remaining Work for Current Milestone (M3.3)

1. Publish component-level token baseline for alerts and empty-state variants.
2. Expand non-shell focus assertions to selected workspace toolbars beyond modal controls.
3. Implement non-core decorative theme token remediations required for M4 hard-gate promotion.

## 7) Risks

- Non-core decorative themes currently have advisory contrast gaps and are not yet hard-gated.
- Focus behavior consistency across less-used routes still requires M3.2 audits.

## 8) Next Action Queue

1. Draft and publish M3.3 component baseline doc (buttons/inputs/alerts/empty states).
2. Convert non-core theme advisory failures into an owned remediation checklist by theme/token pair.
3. Wire M4 all-theme hard-gate promotion tasks into release checklist language.
