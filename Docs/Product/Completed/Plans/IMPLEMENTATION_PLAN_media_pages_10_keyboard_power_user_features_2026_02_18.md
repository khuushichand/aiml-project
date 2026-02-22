# Implementation Plan: Media Pages - Keyboard Shortcuts and Power User Features

## Scope

Pages/components: keyboard handlers in `ViewMediaPage.tsx`, `MediaReviewPage.tsx`, and `KeyboardShortcutsOverlay.tsx`
Finding IDs: `10.1` through `10.6`

## Finding Coverage

- Preserve strong existing keyboard navigation: `10.1`, `10.2`, `10.3`
- Improve shortcut discoverability and efficiency: `10.4`, `10.6`
- Add scoped in-content find capability: `10.5`

## Stage 1: Shortcut Discoverability and Search Focus
**Goal**: Make key shortcuts visible and faster to use.
**Success Criteria**:
- Hint text appears when selection count exceeds 5, explaining double-Escape clear behavior.
- `/` shortcut focuses media search input without interfering with typing contexts.
- Shortcuts overlay reflects new hints and bindings.
**Tests**:
- Integration tests for `/` focus behavior with input-field conflict guards.
- Component tests for conditional double-Escape hint visibility.
- Regression tests for existing shortcut overlay content and open/close controls.
**Status**: Complete

## Stage 2: Scoped Content Find Bar
**Goal**: Provide Ctrl+F-like search limited to the active content pane.
**Success Criteria**:
- In-content find bar opens with dedicated shortcut and focuses input.
- Matches are navigable (next/previous) and scoped to content container only.
- Find state resets safely when switching media items.
**Tests**:
- Unit tests for in-content find matcher and navigation index behavior.
- Integration tests for open/find/next/previous flows.
- Regression tests for browser default find behavior not being blocked globally.
**Status**: Complete

## Stage 3: Regression Safety for Existing Keyboard Workflows
**Goal**: Keep current keyboard strengths intact while adding new controls.
**Success Criteria**:
- `j/k` item navigation remains correct in both `/media` and `/media-multi`.
- Arrow pagination behavior remains unchanged.
- `?` overlay remains accessible with focus trap and Escape handling.
**Tests**:
- Keyboard regression tests for item/page navigation.
- Accessibility tests for overlay dialog semantics.
- Cross-page shortcut conflict tests.
**Status**: Complete

## Dependencies

- Stage 2 should align with content rendering constraints from Category 3.
