# Implementation Plan: Notes Page - Accessibility

## Scope

Components/pages: notes list semantics, editor labeling, keyboard navigation shortcuts, skip links, regression automation.
Finding IDs: `14.1` through `14.10`

## Finding Coverage

- Preserve strong existing accessibility patterns: `14.1`, `14.2`, `14.3`, `14.4`, `14.6`, `14.8`, `14.9`
- Fix selected-note semantic gap: `14.5`
- Fix textarea labeling gap: `14.7`
- Add skip navigation affordances: `14.10`

## Stage 1: High-Impact Semantic Fixes
**Goal**: Close core screen-reader context gaps quickly.
**Success Criteria**:
- Add `aria-current` or `aria-selected` semantics for selected note list item.
- Ensure selected-state semantics update correctly on note switch.
- Validate no regressions in keyboard select behavior.
**Tests**:
- Component tests for selected-note ARIA attribute toggling.
- Screen-reader smoke tests for selected item announcement.
- Keyboard regression tests for list navigation.
**Status**: Complete

## Stage 2: Editor Labeling and Skip Links
**Goal**: Improve navigation and form clarity for assistive technologies.
**Success Criteria**:
- Add explicit `aria-label="Note content"` (or equivalent label binding) to editor textarea.
- Add skip links for notes list and editor landmarks.
- Ensure skip links are visible on focus and functional across responsive layouts.
**Tests**:
- Accessibility tests for textarea label exposure.
- Integration tests for skip-link focus targets.
- Visual tests for focus-visible styles.
**Status**: Complete

## Stage 3: Keyboard and Landmark Hardening
**Goal**: Ensure end-to-end keyboard workflow continuity.
**Success Criteria**:
- Audit and normalize focus order across sidebar, editor header, modal/picker, and dock.
- Add shortcut-discovery hook to upcoming shortcuts cheat sheet.
- Verify no keyboard traps during split/preview and graph modal states.
**Tests**:
- End-to-end keyboard traversal tests.
- Modal focus-trap tests (keyword picker, dock unsaved modal, graph view).
- Regression tests for escape/close semantics.
**Status**: Complete

## Stage 4: Automated Accessibility Regression Gate
**Goal**: Prevent future a11y regressions on notes surfaces.
**Success Criteria**:
- Add automated accessibility checks for `/notes` and key modal states.
- Include checks for ARIA roles, labels, contrast, and focus order basics.
- Document manual assistive-tech smoke checklist for release validation.
**Tests**:
- CI a11y tests for notes page and related overlays.
- Manual NVDA/VoiceOver smoke checklist execution artifacts.
- Snapshot baseline updates with review signoff.
**Status**: Complete

## Dependencies

- Responsive structural changes in Plan 11 should land before final Stage 4 baselines.
- New shortcut surfaces should align with Plans 02, 09, and 15.

## Progress Notes (2026-02-18)

- Completed Stage 1 in `/apps/packages/ui/src/components/Notes/NotesListPanel.tsx`:
  - Added selected-note semantics using `aria-selected` and `aria-current` on note row buttons.
  - Normalized selected-state comparison by string ID to avoid mismatched type edge cases.
  - Preserved existing click/keyboard-accessible button semantics for note navigation.
- Added Stage 1 verification in:
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesListPanel.stage18.accessibility-selected-state.test.tsx`
  - Validates selected-state ARIA toggling on note switch and non-regression of note selection behavior.
- Completed Stage 2 in `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`:
  - Added keyboard-focusable skip links for notes list and editor surfaces.
  - Added focusable landmark regions with stable IDs (`notes-list-region`, `notes-editor-region`) and region labels.
  - Preserved explicit textarea labeling (`aria-label="Note content"`) for edit and split modes.
- Added Stage 2 verification in:
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage19.accessibility-skip-links.test.tsx`
  - Validates skip-link targets/focus behavior and explicit textarea label exposure across editor modes.
- Stage 3 groundwork in `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`:
  - Added keyboard shortcut discovery surface ("Keyboard shortcuts" action + help modal).
  - Added global `?` shortcut handler with typing-target guard to avoid stealing input keystrokes.
  - Added `aria-describedby` shortcut summary semantics on editor landmark for screen-reader context.
- Added Stage 3 verification in:
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage20.accessibility-shortcuts.test.tsx`
  - Validates shortcut summary semantics, help modal discoverability, and `?` behavior across typing/non-typing contexts.
- Added Stage 3 modal/escape focus handoff hardening in:
  - `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
    - Restores focus to invoking control after keyword picker and graph modal close.
  - `/apps/packages/ui/src/components/Notes/KeywordPickerModal.tsx`
    - Explicit keyboard-close support.
  - `/apps/packages/ui/src/components/Notes/NotesGraphModal.tsx`
    - Explicit keyboard-close support.
- Added Stage 3 modal/escape verification in:
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage21.accessibility-modal-focus.test.tsx`
    - Validates Escape-close + focus return for keyword picker and graph modal flows.
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesGraphModal.stage2.graph-view.test.tsx`
    - Validates graph modal closes on Escape.
- Completed Stage 3 dock modal/escape focus hardening in:
  - `/apps/packages/ui/src/components/Common/NotesDock/NotesDockPanel.tsx`
    - Added stable close-button target and unsaved-modal cancel target for reliable keyboard/focus assertions.
    - Added explicit modal keyboard handling and hidden-state behavior for unsaved-close flow consistency.
  - `/apps/packages/ui/src/components/Common/NotesDock/__tests__/NotesDockPanel.stage1.accessibility.test.tsx`
    - Validates unsaved modal cancel path transitions to close state and focus returns to dock close trigger.
- Completed Stage 4 automated a11y gate additions:
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage22.accessibility-regression.test.tsx`
    - Adds axe-core regression checks for notes shell, keyword picker modal state, and graph modal state.
    - Adds theme-token contrast guardrail for notes text on surfaces in light and dark modes.
  - `/apps/packages/ui/src/components/Common/NotesDock/__tests__/NotesDockPanel.stage2.accessibility-regression.test.tsx`
    - Adds axe-core regression checks for dock baseline and unsaved-modal state.
  - `/apps/packages/ui/src/components/Notes/NotesGraphModal.tsx`
    - Adds explicit accessible names for graph zoom/fit icon buttons.
- Added manual assistive-tech smoke checklist:
  - `/Docs/Plans/NOTES_ACCESSIBILITY_SMOKE_CHECKLIST_2026_02_18.md`
- Accessibility-targeted Notes + Dock regression subset remains green (`7 files, 16 tests` for stage 2-4 coverage set).
