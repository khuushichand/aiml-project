# M3 Execution Plan: Design System and Accessibility Baseline

Status: Complete (Engineering)  
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
| M3.3 | Mar 3-Mar 10, 2026 | Component baseline and release gates | Complete (Engineering) | Button/input/alert/empty-state baseline published and referenced in release checklist |

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
  - `Docs/Product/Completed/WebUI-related/M3_3_NonCore_Theme_Contrast_HardGate_Decision_2026_02.md`
- Published M3.3 component token baseline for alert/empty-state variants:
  - `Docs/Product/Completed/WebUI-related/M3_3_Component_Baseline_Alerts_EmptyStates_2026_02.md`
- Added M3 accessibility release-gate checklist linkage:
  - `Docs/Product/Completed/WebUI-related/M3_Release_Checklist_A11y_Baseline_2026_02.md`
- Committed owned M4 non-core theme remediation backlog by theme/token pair:
  - `Docs/Product/Completed/WebUI-related/M4_NonCore_Theme_Contrast_Remediation_Checklist_2026_02.md`
- Remediated non-core decorative theme contrast token pairs (solarized/nord/rose-pine):
  - `apps/packages/ui/src/themes/presets.ts`
- Promoted contrast hard-gate coverage to all shipped built-in themes:
  - `apps/packages/ui/src/themes/__tests__/contrast-baseline.test.ts`
- Expanded non-shell toolbar focus contracts (folders, timeline, document viewer):
  - `apps/packages/ui/src/components/Folders/FolderToolbar.tsx`
  - `apps/packages/ui/src/components/Timeline/TimelineToolbar.tsx`
  - `apps/packages/ui/src/components/DocumentWorkspace/DocumentViewer/ViewerToolbar.tsx`
- Added focus-visible regression tests for toolbars and empty/error actions:
  - `apps/packages/ui/src/components/Folders/__tests__/FolderToolbar.focus.test.tsx`
  - `apps/packages/ui/src/components/Timeline/__tests__/TimelineToolbar.focus.test.tsx`
  - `apps/packages/ui/src/components/DocumentWorkspace/DocumentViewer/__tests__/ViewerToolbar.focus.test.tsx`
  - `apps/packages/ui/src/components/Common/__tests__/FeatureEmptyState.test.tsx`
  - `apps/packages/ui/src/components/Common/__tests__/RouteErrorBoundary.test.tsx`

## 5) Validation Evidence

- `bunx vitest run ../packages/ui/src/themes/__tests__/contrast-baseline.test.ts ../packages/ui/src/components/Layouts/__tests__/ChatHeader.test.tsx ../packages/ui/src/components/Common/ChatSidebar/__tests__/shortcut-active.test.ts`
  - Outcome: `11 passed`
- `bunx vitest run ../packages/ui/src/components/Common/__tests__/CommandPalette.shortcuts.test.tsx ../packages/ui/src/components/Common/__tests__/KeyboardShortcutsModal.focus.test.tsx ../packages/ui/src/components/Layouts/__tests__/ChatHeader.test.tsx ../packages/ui/src/themes/__tests__/contrast-baseline.test.ts`
  - Outcome: `9 passed`
- `TLDW_E2E_SERVER_URL=127.0.0.1:8000 TLDW_E2E_API_KEY=THIS-IS-A-SECURE-KEY-123-FAKE-KEY bunx playwright test e2e/smoke/all-pages.spec.ts --grep "Key Navigation|Wayfinding|Route Error Boundaries" --reporter=line`
  - Outcome: `25 passed` (post-M3 modal-focus regression gate)
- `TLDW_SERVER_URL=http://127.0.0.1:8000 TLDW_API_KEY=THIS-IS-A-SECURE-KEY-123-FAKE-KEY bunx playwright test e2e/smoke/m3-2-a11y-focus-evidence.spec.ts --reporter=line`
  - Outcome: `2 passed` (desktop + mobile route-matrix capture)
- `bunx vitest run ../packages/ui/src/components/Folders/__tests__/FolderToolbar.focus.test.tsx ../packages/ui/src/components/Timeline/__tests__/TimelineToolbar.focus.test.tsx ../packages/ui/src/components/DocumentWorkspace/DocumentViewer/__tests__/ViewerToolbar.focus.test.tsx ../packages/ui/src/components/Common/__tests__/FeatureEmptyState.test.tsx ../packages/ui/src/components/Common/__tests__/RouteErrorBoundary.test.tsx ../packages/ui/src/components/Common/__tests__/CommandPalette.shortcuts.test.tsx ../packages/ui/src/components/Common/__tests__/KeyboardShortcutsModal.focus.test.tsx ../packages/ui/src/themes/__tests__/contrast-baseline.test.ts`
  - Outcome: `18 passed`
- `TLDW_SERVER_URL=http://127.0.0.1:8000 TLDW_API_KEY=THIS-IS-A-SECURE-KEY-123-FAKE-KEY bunx playwright test e2e/smoke/all-pages.spec.ts --grep "Key Navigation Targets|Wayfinding|Route Error Boundaries" --reporter=line`
  - Outcome: `25 passed` (post-toolbar + component-baseline regression gate)
- `TLDW_SERVER_URL=http://127.0.0.1:8000 TLDW_API_KEY=THIS-IS-A-SECURE-KEY-123-FAKE-KEY bunx playwright test e2e/smoke/invalid-api-key.spec.ts --reporter=line`
  - Outcome: `1 passed` (auth-error degradation gate intact)
- `bun /tmp/m4_contrast_audit.ts`
  - Outcome: no failures (all built-in themes satisfy current text/focus thresholds)
- `bun /tmp/m4_pair_ratios.ts`
  - Outcome: recorded patched pair ratios for solarized/nord/rose-pine in `Docs/Product/Completed/WebUI-related/M4_NonCore_Theme_Contrast_Remediation_Checklist_2026_02.md`
- `TLDW_SERVER_URL=http://127.0.0.1:8000 TLDW_API_KEY=THIS-IS-A-SECURE-KEY-123-FAKE-KEY bunx playwright test e2e/smoke/all-pages.spec.ts --grep "Key Navigation Targets|Wayfinding|Route Error Boundaries" --reporter=line`
  - Outcome: `25 passed` (post all-theme hard-gate promotion)
- `TLDW_SERVER_URL=http://127.0.0.1:8000 TLDW_API_KEY=THIS-IS-A-SECURE-KEY-123-FAKE-KEY bunx playwright test e2e/smoke/invalid-api-key.spec.ts --reporter=line`
  - Outcome: `1 passed` (post all-theme hard-gate promotion)

## 6) Remaining Work for Current Milestone (M3.3)

1. QA + accessibility sign-off against `Docs/Product/Completed/WebUI-related/M3_Release_Checklist_A11y_Baseline_2026_02.md`.

## 7) Risks

- Focus behavior consistency across less-used routes still requires M3.2 audits.

## 8) Next Action Queue

1. Run QA/accessibility sign-off using M3 release checklist template.
2. Keep all-theme contrast gate green as part of release-candidate validation.
3. Transition to M4 onboarding flow implementation workstream.
