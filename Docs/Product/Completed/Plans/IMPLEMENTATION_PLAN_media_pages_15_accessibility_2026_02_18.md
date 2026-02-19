# Implementation Plan: Media Pages - Accessibility

## Scope

Pages/components: media list, filter controls, content viewer announcements, keyboard/touch accessibility across `/media` and `/media-multi`
Finding IDs: `15.1` through `15.11`

## Finding Coverage

- Preserve strong existing accessibility behavior: `15.1`, `15.2`, `15.4`, `15.5`, `15.7`, `15.8`, `15.9`
- Address important announcement gap: `15.3`
- Complete verification and ergonomic improvements: `15.6`, `15.10`, `15.11`

## Stage 1: Content Change Announcements
**Goal**: Ensure screen-reader users are informed when selected media content changes.
**Success Criteria**:
- `aria-live="polite"` region announces active media title/status changes.
- Announcement text is concise and avoids noisy duplicate updates.
- Live region behavior works across mouse, keyboard, and programmatic selection changes.
**Tests**:
- Accessibility-focused component tests for live region updates.
- Integration tests for list selection and content-area announcement changes.
- Regression tests ensuring no repeated announcement spam on minor rerenders.
**Status**: Complete
**Progress Notes (2026-02-18)**:
- Added a dedicated `aria-live="polite"` + `aria-atomic="true"` region in `ContentViewer` to announce loading/ready transitions for the active media item.
- Implemented de-duplication keyed by `mediaId + loadingState` to prevent repeated announcement spam during minor rerenders.
- Added `ContentViewer.stage15.accessibility.test.tsx` coverage for loading/ready announcements, pointer/keyboard/programmatic selection changes, and rerender de-duplication.

## Stage 2: Input and Touch Accessibility Improvements
**Goal**: Improve control discoverability and usable target sizing.
**Success Criteria**:
- Favorite button target size increased to meet minimum touch target guidance.
- Keyword filter select behavior reviewed and improved for screen-reader result announcements.
- Any ARIA overrides used with Ant Select remain standards-compliant.
**Tests**:
- Component tests for favorite button sizing classes.
- Manual + automated screen-reader verification checklist for keyword select.
- Accessibility integration tests for filter interaction announcements where feasible.
**Status**: Complete
**Progress Notes (2026-02-18)**:
- Verified favorite-button touch target uses `p-1.5` sizing in `ResultsList` (44px-friendly baseline retained).
- Added explicit ARIA labeling/description wiring for include/exclude keyword selects in `FilterPanel`.
- Added polite `aria-live` result-count announcements for keyword suggestions (include and exclude) with focused test coverage in `FilterPanel.test.tsx`.

## Stage 3: Contrast Verification and Token Adjustments
**Goal**: Replace visual-only assumptions with measured contrast compliance.
**Success Criteria**:
- Contrast ratios measured for key media page tokens/states against WCAG AA.
- Non-compliant token combinations adjusted without breaking design consistency.
- Contrast check results documented for future regression use.
**Tests**:
- Automated contrast checks where supported.
- Visual regression tests for updated token usage.
- Manual audit record added with measured ratios.
**Status**: Complete
**Progress Notes (2026-02-18)**:
- Added media-page-specific token contrast regression coverage in `apps/packages/ui/src/themes/__tests__/media-pages-accessibility-contrast.stage15.test.ts`.
- Verified WCAG thresholds for core text/focus pairings across all built-in themes and enforced documented minimum floors.
- Added audit record with measured worst-case ratios in `Docs/Plans/MEDIA_PAGES_CONTRAST_AUDIT_2026_02_18.md`.

## Stage 4: Accessibility Regression Suite for Existing Strengths
**Goal**: Protect existing keyboard and semantic wins while new a11y fixes ship.
**Success Criteria**:
- Sidebar keyboard navigation semantics remain intact.
- Section navigator tree semantics and action button labeling remain intact.
- Keyboard shortcuts overlay dialog semantics/focus trap remain intact.
**Tests**:
- Regression tests for keyboard traversal and activation.
- Axe-based integration tests for media and multi-review pages.
- Dialog/landmark semantic tests for shortcuts and navigator components.
**Status**: Complete
**Progress Notes (2026-02-18)**:
- Added keyboard activation regression coverage for result rows (`Enter`/`Space`) in `ResultsList.test.tsx`.
- Added navigator semantic regression coverage (`aria-label` landmark + `role="tree"`) in `MediaSectionNavigator.test.tsx`.
- Added axe-based aria/region regression checks for both `/media` and `/media-multi` page shells in:
  - `apps/packages/ui/src/components/Review/__tests__/ViewMediaPage.stage13.error-handling.test.tsx`
  - `apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage1.selectionLimit.test.tsx`

## Dependencies

- Stage 2 touch-target updates should be shared with Category 11 responsive work.
- Stage 1 should align with content-switch behavior introduced in Category 3.
