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
**Status**: Complete

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
**Status**: Complete

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
**Status**: Complete

## Dependencies

- Final responsive DOM structure should precede Plan 14 final accessibility sweep.
- Dock behavior should stay aligned with Plan 09 keyboard/sync semantics.

## Progress Notes (2026-02-18)

- Completed Stage 1 in `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`:
  - Added mobile single-panel behavior with slide-over notes list and backdrop (`<768px`).
  - Replaced fixed desktop sidebar width contract with responsive width steps (`300/340/380`).
  - Added automatic mobile collapse and desktop collapse-state restoration when crossing breakpoints.
  - Added mobile notes-list opener and close-on-select behavior for note navigation.
- Added Stage 1 verification in:
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage23.responsive-layout.test.tsx`
  - Covers responsive behavior at `320/375/768/1024`, desktop collapse-state restoration, and note-selection persistence across mode switches.
- Completed Stage 2 in:
  - `/apps/packages/ui/src/components/Notes/NotesEditorHeader.tsx`
    - Added mobile touch-target sizing (`min-h-[44px]`) for primary editor toolbar controls.
    - Added mobile wrapped toolbar layout while preserving compact desktop density.
  - `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
    - Upgraded mobile notes-list opener to touch-size target (`>=44px`).
- Added Stage 2 verification in:
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesEditorHeader.stage2.touch-layout.test.tsx`
  - Validates mobile wrapped layout + touch target classes and desktop compact behavior.
- Completed Stage 3 in:
  - `/apps/packages/ui/src/components/Common/NotesDock/NotesDockButton.tsx`
    - Hides dock trigger on mobile viewports.
  - `/apps/packages/ui/src/components/Common/NotesDock/NotesDockHost.tsx`
    - Prevents dock panel rendering on mobile while preserving existing open/unsaved dock state for desktop return (no forced close on breakpoint transition).
- Added Stage 3 verification in:
  - `/apps/packages/ui/src/components/Common/NotesDock/__tests__/NotesDockButton.stage3.responsive.test.tsx`
  - `/apps/packages/ui/src/components/Common/NotesDock/__tests__/NotesDockHost.stage3.responsive.test.tsx`
  - Confirms dock trigger/panel desktop visibility and mobile suppression behavior.
