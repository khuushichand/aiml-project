# M3 Release Checklist: Accessibility Baseline

Status: Active Template  
Owner: WebUI + QA  
Date: February 13, 2026  
Related: `Docs/Product/Completed/WebUI-related/M3_Design_System_A11y_Execution_Plan_2026_02.md`

## 1) Gate Scope

Use this checklist for any release candidate that touches:

1. Theme tokens or component styling
2. Keyboard/focus behavior
3. Alert/empty state UX in core or non-core routes

## 2) Required Evidence

- [ ] Core contrast gate passes:
  - `bunx vitest run ../packages/ui/src/themes/__tests__/contrast-baseline.test.ts`
- [ ] Modal focus contracts pass:
  - `bunx vitest run ../packages/ui/src/components/Common/__tests__/CommandPalette.shortcuts.test.tsx ../packages/ui/src/components/Common/__tests__/KeyboardShortcutsModal.focus.test.tsx`
- [ ] Non-shell toolbar/empty-state focus contracts pass:
  - `bunx vitest run ../packages/ui/src/components/Folders/__tests__/FolderToolbar.focus.test.tsx ../packages/ui/src/components/Timeline/__tests__/TimelineToolbar.focus.test.tsx ../packages/ui/src/components/DocumentWorkspace/DocumentViewer/__tests__/ViewerToolbar.focus.test.tsx ../packages/ui/src/components/Common/__tests__/FeatureEmptyState.test.tsx ../packages/ui/src/components/Common/__tests__/RouteErrorBoundary.test.tsx`
- [ ] Route matrix keyboard evidence present for desktop and mobile:
  - `Docs/Product/Completed/WebUI-related/WebUI_UX_Evidence_Artifact_Index_2026_02.md`

## 3) M3.3 Hard-Gate Rules

- [ ] No regression in core theme AA checks (`default`, `high-contrast`).
- [ ] No regression in focus-visible ring classes on audited controls.
- [ ] Alert and empty-state implementations align with:
  - `Docs/Product/Completed/WebUI-related/M3_3_Component_Baseline_Alerts_EmptyStates_2026_02.md`

## 4) M4+ Hard-Gate Rules (Stop-Ship)

- [ ] All built-in themes pass contrast baseline checks (`default`, `high-contrast`, `solarized`, `nord`, `rose-pine`) in:
  - `../packages/ui/src/themes/__tests__/contrast-baseline.test.ts`
- [ ] Any non-core contrast regression is treated as release-blocking for M4+.
- [ ] Remediation backlog evidence reviewed and closed:
  - `Docs/Product/Completed/WebUI-related/M4_NonCore_Theme_Contrast_Remediation_Checklist_2026_02.md`

## 5) Sign-Off

- [ ] QA sign-off
- [ ] Accessibility sign-off
- [ ] WebUI owner sign-off
