# PR 840 Qodo Review Items Plan

## Stage 1: Reproduce the reported regressions
**Goal**: Add focused tests that fail on the current review-page implementation.
**Success Criteria**: New tests cover scroll-sync rebinding, mixed string/number selection ids, and global shortcut suppression on focused interactive controls.
**Tests**: `ComparisonSplit.test.tsx`, `MediaReviewPage.stage6.keyboard-scope.test.tsx`, `MediaReviewPage.stage7.three-panel.test.tsx`
**Status**: Complete

## Stage 2: Apply minimal behavior fixes
**Goal**: Patch the review hooks/components without widening scope.
**Success Criteria**: Sync-scroll rebinds after comparison panel remounts, selection logic treats `"1"` and `1` as the same id everywhere in the results path, and buttons/links no longer get hijacked by global shortcuts.
**Tests**: Targeted Vitest files from Stage 1
**Status**: Complete

## Stage 3: Verify and close out
**Goal**: Confirm the fixes pass targeted tests and capture PR follow-up.
**Success Criteria**: Targeted test suite passes and remaining PR-thread work is clearly identified.
**Tests**: `bunx vitest run` for the touched test files
**Status**: Complete
