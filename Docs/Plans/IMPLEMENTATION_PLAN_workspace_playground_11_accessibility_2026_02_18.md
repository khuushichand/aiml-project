# Implementation Plan: Workspace Playground - Accessibility

## Scope

Components: Workspace Playground panes, icon-only controls, collapsible sections, landmarks, contrast tokens
Finding IDs: `11.1` through `11.11`

## Finding Coverage

- Preserve good implemented patterns: `11.1`, `11.2`, `11.6`, `11.7`, `11.10`
- Critical semantic/accessibility gaps: `11.3`, `11.4`, `11.11`
- Interaction and visibility fixes: `11.5`
- Contrast compliance checks: `11.8`, `11.9`

## Stage 1: Critical ARIA and Landmark Remediation
**Goal**: Close critical screen-reader discoverability and control-label gaps.
**Success Criteria**:
- Collapsible Studio sections expose `aria-expanded` and `aria-controls`.
- All icon-only buttons include explicit `aria-label` values.
- Workspace layout adds skip navigation links and explicit labels for complementary asides.
**Tests**:
- Component tests asserting required ARIA attributes on collapsibles.
- Audit test detecting icon-only buttons missing `aria-label`.
- Accessibility integration test for skip-link focus target behavior.
**Status**: Complete

## Stage 2: Focus and Visibility Parity
**Goal**: Ensure controls hidden visually remain discoverable for keyboard and touch users.
**Success Criteria**:
- Remove button becomes visible on `:focus-visible`.
- Touch devices show non-hover controls via responsive CSS behavior.
- Keyboard traversal order remains logical after visibility changes.
**Tests**:
- Component tests for focus-visible style state.
- Mobile viewport tests for always-visible critical controls.
- Keyboard navigation integration test across panes.
**Status**: Complete

## Stage 3: Contrast Audit and Regression Gates
**Goal**: Verify color usage meets WCAG AA and stays compliant.
**Success Criteria**:
- `text-muted`/surface and success badge combinations audited and corrected as needed.
- Workspace playground color tokens meet AA thresholds for text/UI components.
- Automated a11y checks (axe-based) added to workspace test suite.
**Tests**:
- Automated contrast assertions where feasible.
- Axe integration test for workspace page.
- Manual audit checklist added to docs with measured contrast values.
**Status**: Complete

## Dependencies

- Touch visibility work should align with responsive fixes in Category 7.

## Progress Notes (2026-02-18)

- Stage 1 completed:
  - Added explicit skip-navigation links in workspace layout:
    - skip to chat content,
    - skip to sources panel,
    - skip to studio panel.
  - Added explicit landmark semantics for the desktop three-pane layout:
    - labeled complementary `aside` regions for Sources/Studio,
    - stable main content anchor id for skip-link targeting.
  - Added ARIA state metadata for Studio collapsible controls:
    - `aria-expanded` + `aria-controls` on Output Types and Generated Outputs toggles,
    - `aria-expanded` + `aria-controls` for audio settings disclosure.
  - Added audit coverage ensuring icon-only studio action buttons expose `aria-label`.

- Stage 1 files updated:
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/index.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/index.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage3.test.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage3.test.tsx`

- Stage 1 validation:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage1.test.tsx src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage3.test.tsx src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage3.test.tsx src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage9.persistence.test.tsx --reporter=verbose`

- Stage 2 completed:
  - Retained and validated focus-visible/touch parity behavior for source remove actions:
    - keyboard users can reveal and focus remove controls (`focus-visible` path),
    - touch devices always expose non-hover controls (`@media (hover: none)` path).
  - Added keyboard-order regression coverage inside source rows to ensure navigation remains logical between selection and destructive controls.

- Stage 2 files updated:
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage2.test.tsx`

- Stage 2 validation:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage2.test.tsx --reporter=verbose`

- Stage 3 completed:
  - Remediated mobile tab count badge contrast by replacing `text-white` on accent fills with AA-safe token pairing (`text-text` on `bg-surface2`) in Workspace Playground mobile tabs.
  - Added targeted contrast regression tests for:
    - source icon pairing (`textMuted/surface2`),
    - mobile tab badge pairing (`text/surface2`).
  - Added an axe-core integration test in workspace playground coverage focused on landmark and naming rules.
  - Added a manual contrast audit checklist and measured values document.

- Stage 3 files updated:
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/index.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage2.responsive.test.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage3.test.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage11.contrast.test.ts`
  - `apps/packages/ui/package.json`
  - `Docs/Reviews/WORKSPACE_PLAYGROUND_A11Y_CONTRAST_AUDIT_2026_02_18.md`

- Stage 3 validation:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage2.responsive.test.tsx src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage3.test.tsx src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage11.contrast.test.ts --reporter=verbose`
