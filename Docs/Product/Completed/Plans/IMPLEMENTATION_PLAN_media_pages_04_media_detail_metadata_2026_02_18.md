# Implementation Plan: Media Pages - Media Detail and Metadata

## Scope

Pages/components: media detail header and metadata surfaces in `ContentViewer.tsx` and result-detail transitions
Finding IDs: `4.1` through `4.8`

## Finding Coverage

- Preserve current strong detail affordances: `4.1`, `4.3`, `4.4`
- Close important metadata context gaps: `4.2`, `4.7`
- Add secondary metadata visibility improvements: `4.5`, `4.6`, `4.8`

## Stage 1: Metadata Bar Baseline
**Goal**: Add core freshness and reading context directly under media title.
**Success Criteria**:
- Ingestion date and last-modified timestamps displayed in detail header metadata bar.
- Word count and estimated reading time surfaced prominently.
- Date formatting is consistent with result-list date display standards.
**Tests**:
- Component tests for metadata bar rendering with/without date values.
- Unit tests for reading-time estimator and fallback behavior.
- Snapshot tests for compact and expanded header layouts.
**Status**: Complete

Progress Notes (2026-02-18):
- Added metadata-bar freshness indicators in `ContentViewer`:
  - `Ingested <relative time>` using compact relative formatter
  - `Updated <relative time>` using compact relative formatter
- Surfaced reading context directly in the metadata bar:
  - Existing word count remains visible
  - Added estimated reading-time label (`N min read`)
- Added helper utility `mediaMetadataUtils.ts` with reading-time estimator and fallback to character-based estimate when word count is unavailable.
- Added Stage 1 test coverage:
  - `src/components/Media/__tests__/ContentViewer.stage1.test.tsx`
  - `src/components/Media/__tests__/mediaMetadataUtils.test.ts`

## Stage 2: Rich Metadata and Processing Status
**Goal**: Surface high-value academic/system metadata without cluttering primary view.
**Success Criteria**:
- Expandable metadata section renders DOI, PMID, journal, license, and related safe fields.
- Processing status badges added for chunking/vector processing states.
- Missing metadata states handled gracefully with clear empty-state copy.
**Tests**:
- Component tests for expandable metadata sections and field-level conditional rendering.
- Integration tests for status badge transitions from API payloads.
- Regression tests for keyword edit controls in presence of new metadata section.
**Status**: Complete

Progress Notes (2026-02-18):
- Added safe metadata extraction and prioritization in `ContentViewer` with display ordering for `DOI`, `PMID`, `PMCID`, `arXiv`, `Journal`, and `License` before remaining fields.
- Added normalized processing-state badges for chunking/vector states (handles numeric, boolean-like, and string payloads).
- Added expandable metadata details panel under the primary metadata bar:
  - Shows processing badges and additional metadata fields when available.
  - Shows explicit empty-state copy when processing or safe metadata are absent.
- Preserved keyword edit visibility and added stable test selector (`data-testid="media-keywords-select"`) for regression coverage.
- Added Stage 2 tests:
  - `apps/packages/ui/src/components/Media/__tests__/ContentViewer.metadataStage2.test.tsx`

## Stage 3: Deep-Linkability and Permalinks
**Goal**: Enable shareable, direct links to media details.
**Success Criteria**:
- Media item ID can be reflected in URL query/state (`?id=` or route equivalent).
- Opening permalink restores selected item and expected viewer state.
- Existing last-selected-item behavior remains backwards compatible.
**Tests**:
- Router integration tests for direct-link load behavior.
- Regression test for legacy `LAST_MEDIA_ID_SETTING` restore behavior.
- Navigation tests for previous/next controls while deep-linked.
**Status**: Complete

Progress Notes (2026-02-18):
- Added permalink utilities:
  - `apps/packages/ui/src/components/Review/mediaPermalink.ts`
  - `apps/packages/ui/src/components/Review/__tests__/mediaPermalink.test.ts`
- Wired `ViewMediaPage` to:
  - Read `?id=<mediaId>` and prioritize it as initial selection.
  - Fall back to legacy `LAST_MEDIA_ID_SETTING` when no permalink is present.
  - Hydrate a deep-linked media item directly from `/api/v1/media/{id}` when not in the current page of results.
  - Persist selected media back to `LAST_MEDIA_ID_SETTING`.
  - Keep URL `?id=` synchronized with current media selection (replace navigation).
- Added Stage 3 integration tests in:
  - `apps/packages/ui/src/components/Review/__tests__/ViewMediaPage.permalink.test.tsx`
  - Covers direct-link hydration, legacy setting fallback, and previous/next permalink sync.

## Stage 4: Regression Hardening for Existing Strengths
**Goal**: Keep current high-quality metadata interactions stable.
**Success Criteria**:
- Title/type/source URL header content remains clear and functional.
- Duration display for audio/video remains unchanged.
- Inline keyword editing save cadence and debounce remain stable.
**Tests**:
- Regression tests for title/source link rendering.
- Component tests for duration visibility conditions.
- Integration tests for debounced keyword save behavior.
**Status**: Complete

Progress Notes (2026-02-18):
- Added metadata regression coverage in:
  - `apps/packages/ui/src/components/Media/__tests__/ContentViewer.stage4.metadataRegression.test.tsx`
- Verified baseline behaviors remain stable:
  - Header still renders title/type/source metadata.
  - Duration badge remains visible only when a valid duration exists.
  - Keyword edit save remains debounced (500ms) and sends latest keyword state.

## Dependencies

- Stage 1 and Stage 2 should share date/stat formatting utilities with Category 1 and Category 3.
