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
**Status**: Not Started

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
**Status**: Not Started

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
**Status**: Not Started

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
**Status**: Not Started

## Dependencies

- Responsive structural changes in Plan 11 should land before final Stage 4 baselines.
- New shortcut surfaces should align with Plans 02, 09, and 15.
