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
| M3.2 | Feb 20-Mar 3, 2026 | Keyboard/focus path normalization | In Progress | Core workflows pass keyboard/focus QA script and targeted tests |
| M3.3 | Mar 3-Mar 10, 2026 | Component baseline and release gates | Not Started | Button/input/alert/empty-state baseline published and referenced in release checklist |

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

## 5) Validation Evidence

- `bunx vitest run ../packages/ui/src/themes/__tests__/contrast-baseline.test.ts ../packages/ui/src/components/Layouts/__tests__/ChatHeader.test.tsx ../packages/ui/src/components/Common/ChatSidebar/__tests__/shortcut-active.test.ts`
  - Outcome: `10 passed`

## 6) Remaining Work for Current Milestone (M3.2)

1. Execute keyboard/focus walkthrough evidence capture across the full core route matrix (desktop + mobile).
2. Add targeted focus-visible assertions for remaining high-frequency modal/toolbar entry points.
3. Draft M3.3 hard-gating recommendation for non-core decorative theme contrast.

## 7) Risks

- Non-core decorative themes currently have advisory contrast gaps and are not yet hard-gated.
- Focus behavior consistency across less-used routes still requires M3.2 audits.

## 8) Next Action Queue

1. Run and archive M3.2 route-matrix evidence set under `Docs/Product/WebUI/evidence/`.
2. Expand focus-visible assertions for non-shell controls most used in chat and settings workflows.
3. Finalize M3.3 gating recommendation and backlog cut line.
