# Implementation Plan: Characters - Accessibility

## Scope

Components: `apps/packages/ui/src/components/Option/Characters/Manager.tsx`, `apps/packages/ui/src/components/Option/Characters/CharacterGalleryCard.tsx`, shared styles in `apps/packages/ui/src/assets/tailwind-shared.css`
Finding IDs: `C-27` through `C-30`

## Finding Coverage

- Inline edit is mouse-only due to double-click trigger: `C-27`
- No explicit reduced-motion handling in characters surface: `C-28`
- Missing skip link and main landmark for fast navigation: `C-29`
- Shortcut help visibility is hover-centric and not proactively announced: `C-30`

## Stage 1: Keyboard-Accessible Inline Editing
**Goal**: Ensure inline edit actions are fully keyboard operable.
**Success Criteria**:
- Focusable edit affordance exists for editable cells/fields.
- `Enter`/`F2` keyboard entry path opens inline edit mode.
- Save/cancel flows are keyboard-complete and return focus predictably.
**Tests**:
- Component tests for keyboard trigger and commit/cancel behavior.
- Integration tests for tab order and focus return after inline edit.
- Accessibility tests for role/name/state on edit controls.
**Status**: Complete

## Stage 2: Reduced-Motion Compliance
**Goal**: Respect user motion preferences for characters interactions.
**Success Criteria**:
- Character page transitions/hover effects are reduced or disabled under `prefers-reduced-motion: reduce`.
- Modal and tooltip animations use reduced-motion-safe variants.
- Motion behavior is documented in UI style guidance for this feature.
**Tests**:
- Unit/style tests for reduced-motion media query coverage.
- Manual QA checklist in reduced-motion OS/browser mode.
- Visual checks ensuring no hidden state regressions when transitions are removed.
**Status**: Not Started

## Stage 3: Landmarks and Skip Navigation
**Goal**: Improve non-visual navigation efficiency.
**Success Criteria**:
- Characters content container includes `role="main"` (or semantic `main`).
- Page exposes a top-level skip-to-content link visible on keyboard focus.
- Landmark/heading structure is unambiguous for screen reader navigation.
**Tests**:
- Accessibility tests verifying main landmark and skip-link behavior.
- Keyboard-only E2E test validating skip navigation path.
**Status**: Not Started

## Stage 4: Shortcut Discoverability for Assistive Tech Users
**Goal**: Make keyboard-shortcut guidance available beyond hover tooltips.
**Success Criteria**:
- Shortcut summary is reachable via focus and/or referenced via `aria-describedby`.
- Tooltip trigger supports keyboard focus, not hover-only disclosure.
- Hidden shortcut summary remains synchronized with active shortcuts.
**Tests**:
- Component tests for focus-triggered shortcut help visibility.
- Accessibility test validating `aria-describedby` associations.
- Regression tests for shortcut execution after help system changes.
**Status**: Not Started

## Dependencies

- Stage 2 should leverage existing motion tokens and reduced-motion conventions in shared styles.
- Stage 4 should coordinate with existing `useCharacterShortcuts` hook behavior.
