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
**Status**: Not Started

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
**Status**: Not Started

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
**Status**: Not Started

## Dependencies

- Touch visibility work should align with responsive fixes in Category 7.
