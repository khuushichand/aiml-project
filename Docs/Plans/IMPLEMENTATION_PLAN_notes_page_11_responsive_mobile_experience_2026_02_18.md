# Implementation Plan: Notes Page - Responsive & Mobile Experience

## Scope

Components/pages: `/notes` sidebar/editor layout behavior across breakpoints, touch target sizing, dock behavior on small screens.
Finding IDs: `11.1` through `11.6`

## Finding Coverage

- Preserve positive existing patterns: `11.1`, `11.4`, `11.6`
- Resolve layout compression issues from fixed sidebar width: `11.2`
- Improve touch ergonomics for toolbar controls: `11.3`
- Define mobile dock strategy: `11.5`

## Stage 1: Mobile-First Layout Contract
**Goal**: Prevent cramped dual-pane layout on small screens.
**Success Criteria**:
- Replace fixed 380px sidebar contract with responsive breakpoints.
- Auto-collapse sidebar on small screens and use drawer/sheet navigation pattern.
- Maintain smooth transition and state restoration when returning to desktop widths.
**Tests**:
- Responsive integration tests at 320/375/768/1024 widths.
- Component tests for sidebar auto-collapse/expand behavior.
- Regression tests for note selection persistence across layout mode switches.
**Status**: Not Started

## Stage 2: Touch Target and Toolbar Ergonomics
**Goal**: Meet mobile accessibility sizing expectations.
**Success Criteria**:
- Ensure primary action controls meet >=44px target on touch layouts.
- Introduce responsive toolbar layout (wrapping/grouping) for small viewports.
- Preserve desktop information density where touch constraints are not required.
**Tests**:
- Style/layout tests validating target dimensions at mobile breakpoints.
- Visual regression tests for toolbar wrapping and overflow behavior.
- Accessibility tests for focus order and tappable control spacing.
**Status**: Not Started

## Stage 3: Floating Dock Mobile Behavior
**Goal**: Prevent dock from obscuring entire mobile experience.
**Success Criteria**:
- Hide dock trigger on mobile or convert dock to full-screen overlay mode.
- Keep multi-draft and unsaved-change behavior consistent with desktop expectations.
- Document final behavior and discoverability entry point.
**Tests**:
- Responsive tests for dock visibility/overlay behavior.
- Interaction tests for draft switching and close-protection modal on mobile.
- Regression tests for desktop dock positioning persistence.
**Status**: Not Started

## Dependencies

- Final responsive DOM structure should precede Plan 14 final accessibility sweep.
- Dock behavior should stay aligned with Plan 09 keyboard/sync semantics.
