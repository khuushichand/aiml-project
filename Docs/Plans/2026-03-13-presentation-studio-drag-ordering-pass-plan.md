## Stage 1: Define the focused UX pass
**Goal**: Limit this pass to drag-and-drop slide ordering in the Presentation Studio rail.
**Success Criteria**: The scope stays within store reorder support, sortable rail items, and browser verification.
**Tests**: N/A
**Status**: Complete

## Stage 2: Add regression coverage for drag ordering
**Goal**: Add tests for direct reorder state changes and visible drag handles.
**Success Criteria**: Tests fail before implementation and cover store reorder behavior plus slide-rail affordances.
**Tests**: Vitest store/component tests for `reorderSlides` and drag-handle rendering.
**Status**: Complete

## Stage 3: Implement drag-and-drop ordering
**Goal**: Add sortable slide cards using the repo's existing `@dnd-kit/react` pattern while keeping button-based reorder fallback controls.
**Success Criteria**: Users can drag slide cards to reorder them, and the selected slide/order updates correctly.
**Tests**: Existing and new Vitest tests, plus Playwright browser verification.
**Status**: Complete

## Stage 4: Verify with targeted tests and browser audit
**Goal**: Confirm drag ordering works without regressing the working editor and responsive layout.
**Success Criteria**: Targeted Vitest suite passes and the Presentation Studio Playwright flow verifies reordered slides in the browser.
**Tests**: `bunx vitest run ...`, `bunx playwright test e2e/ux-audit/presentation-studio.spec.ts --project=chromium --reporter=line`
**Status**: Complete
