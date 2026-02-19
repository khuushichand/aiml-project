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
**Status**: Complete

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
**Status**: Complete

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
**Status**: Complete

## Dependencies

- Keyboard shortcut inventory should align with Plan 15 shortcut cheat-sheet scope.
- Mobile breakpoint behavior should align with Plan 11 responsive standards.

## Progress Notes (2026-02-18)

### Stage 1 completion

- Added a global dock toggle shortcut (`Ctrl/Cmd+Shift+N`) in:
  - `/apps/packages/ui/src/components/Common/NotesDock/NotesDockHost.tsx`
- Added restricted-context guards so the shortcut does not fire while typing in inputs, textareas, selects, or contenteditable targets.
- Preserved unsaved-close flow by dispatching existing dock close request event when the shortcut is used while open.
- Added shortcut discoverability metadata on the dock trigger:
  - tooltip hint with `Ctrl/Cmd+Shift+N`
  - `aria-keyshortcuts` attribute
  - file: `/apps/packages/ui/src/components/Common/NotesDock/NotesDockButton.tsx`
- Added Stage 1 tests:
  - `/apps/packages/ui/src/components/Common/NotesDock/__tests__/NotesDockHost.stage1.keyboard-shortcut.test.tsx`
    - open via Ctrl/Cmd variants
    - typing-context suppression
    - close-event dispatch behavior
    - listener teardown on unmount

### Stage 2 completion

- Added cross-surface notes cache refresh after dock saves:
  - `/apps/packages/ui/src/components/Common/NotesDock/NotesDockPanel.tsx`
    - invalidates React Query `["notes"]` queries via shared query client
    - keeps save flow optimistic (`void` background sync) and non-blocking
    - shows minimal sync status text while invalidation is in flight
- Added Stage 2 tests:
  - `/apps/packages/ui/src/components/Common/NotesDock/__tests__/NotesDockPanel.stage4.cache-sync.test.tsx`
    - verifies post-save invalidation and sync-indicator lifecycle

### Stage 3 completion

- Hardened mobile behavior to avoid losing unsaved dock work:
  - `/apps/packages/ui/src/components/Common/NotesDock/NotesDockHost.tsx`
    - no longer force-closes dock state when entering mobile viewport
    - keeps panel hidden on mobile while preserving open/unsaved state for desktop return
- Added desktop-only discoverability copy for dock trigger shortcut:
  - `/apps/packages/ui/src/components/Common/NotesDock/NotesDockButton.tsx`
    - tooltip hint includes desktop-only guidance + shortcut
    - `aria-keyshortcuts` advertises binding to assistive tech
- Updated responsive/behavior tests:
  - `/apps/packages/ui/src/components/Common/NotesDock/__tests__/NotesDockHost.stage3.responsive.test.tsx`
  - `/apps/packages/ui/src/components/Common/NotesDock/__tests__/NotesDockButton.stage3.responsive.test.tsx`
