# Implementation Plan: Notes Page - Floating Notes Dock

## Scope

Components/pages: dock toggle button/panel, draft tabbing, dock->notes-page synchronization and responsive behavior.
Finding IDs: `9.1` through `9.8`

## Finding Coverage

- Preserve strong current dock behavior/accessibility: `9.1`, `9.2`, `9.3`, `9.6`, `9.7`, `9.8`
- Add missing keyboard toggle: `9.4`
- Resolve data consistency between dock and notes page: `9.5`

## Stage 1: Global Keyboard Toggle for Dock
**Goal**: Improve rapid-capture workflow efficiency.
**Success Criteria**:
- Add global shortcut (target: Ctrl/Cmd+Shift+N) to toggle dock visibility.
- Avoid conflicts with existing shortcuts and browser defaults.
- Expose shortcut hint in tooltip/help text.
**Tests**:
- Unit tests for shortcut registration and teardown.
- Integration tests for toggle behavior from multiple app routes.
- Conflict tests to ensure shortcut does not trigger while typing in restricted contexts.
**Status**: Not Started

## Stage 2: Query Cache and Cross-Surface Sync
**Goal**: Keep dock saves and notes page state consistent.
**Success Criteria**:
- Invalidate/refresh relevant React Query caches after dock save/update/delete actions.
- Preserve optimistic dock UX while avoiding stale list data on `/notes`.
- Add minimal sync indicator when background refresh occurs.
**Tests**:
- Integration tests for dock save -> notes list refresh path.
- Regression tests for pagination/filter state persistence after invalidation.
- Error-path tests for failed invalidation and fallback refetch.
**Status**: Not Started

## Stage 3: Mobile Dock Strategy
**Goal**: Prevent viewport takeover on small screens.
**Success Criteria**:
- Hide dock trigger below configured breakpoint or switch to full-screen overlay mode.
- Preserve unsaved-change protections across mobile behavior.
- Document device-specific behavior in user help text.
**Tests**:
- Responsive tests for breakpoint behavior and overlay sizing.
- Interaction tests for unsaved modal actions on mobile mode.
- Accessibility tests for focus-trap integrity in mobile overlay.
**Status**: Not Started

## Dependencies

- Keyboard shortcut inventory should align with Plan 15 shortcut cheat-sheet scope.
- Mobile breakpoint behavior should align with Plan 11 responsive standards.
