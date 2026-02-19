# Implementation Plan: Media Pages - Media Discovery and Browsing

## Scope

Pages/components: `/media` discovery sidebar and results pane (`ViewMediaPage.tsx`, `FilterPanel.tsx`, `ResultsList.tsx`)
Finding IDs: `1.1` through `1.12`

## Finding Coverage

- Core missing discovery controls: `1.1`, `1.2`, `1.8`
- Result context and browsing ergonomics: `1.3`, `1.6`, `1.10`, `1.12`
- Query assistance and autocomplete completeness: `1.4`, `1.7`
- Preserve validated strengths: `1.5`, `1.9`, `1.11`

## Stage 1: Search Control Parity
**Goal**: Expose already-supported backend filtering/sorting controls in the media filter UI.
**Success Criteria**:
- Sort selector added to `FilterPanel` with relevance, date newest/oldest, and title A-Z/Z-A.
- Date range picker added and serialized into `date_range.start`/`date_range.end` in search requests.
- "Exclude keywords" control added and wired to `must_not_have`.
**Tests**:
- Component tests for sort/date/exclude controls rendering and value changes.
- Integration test asserting request payload includes `sort_by`, `date_range`, and `must_not_have`.
- Regression test confirming existing `must_have` behavior remains intact.
**Status**: Complete

## Stage 2: Result Context and Navigation Polish
**Goal**: Improve scanability and reduce repetitive browsing friction.
**Success Criteria**:
- Relative date appears in each result row next to media type.
- Media type filter section behavior improved (auto-expand or top-N + show-all behavior).
- Sidebar collapse state persisted across reloads using existing settings/storage pattern.
- Page size selector (20/50/100) added and wired into pagination state.
**Tests**:
- Snapshot/component test for result-row metadata display.
- State-persistence test for sidebar collapse restoration.
- Pagination integration test covering page size transitions.
**Status**: Complete

## Stage 3: Query Assistance and Keyword Discoverability
**Goal**: Help users form better queries and reduce autocomplete blind spots.
**Success Criteria**:
- Search syntax help tooltip added near search input.
- Keyword autocomplete strategy documented and implemented with graceful fallback.
- If backend keyword endpoint is unavailable, UI clearly indicates autocomplete is result-scoped.
**Tests**:
- Component test for tooltip visibility and content trigger.
- Unit/integration tests for keyword-source fallback path.
- Contract test (or mocked API test) for dedicated keyword endpoint integration.
**Status**: Complete

## Stage 4: Regression Guards for Existing Good Behavior
**Goal**: Preserve proven interaction quality while shipping new controls.
**Success Criteria**:
- Media/notes kind toggle behavior and counts remain unchanged.
- Filter chips retain remove and clear-all behavior.
- JumpToNavigator threshold and accessibility states remain unchanged.
**Tests**:
- Regression tests for toggle, chips, and jump navigator behavior.
- Keyboard/accessibility checks for active/pressed state semantics.
**Status**: Complete

## Dependencies

- `1.7` depends on backend decision for a dedicated keywords listing endpoint.
- Stage 1 request shape changes should align with search plans in Category 2.

## Progress Notes (2026-02-18)

- Completed Stage 1 implementation for findings `1.1`, `1.2`, and `1.8`:
  - Added sort selector (`relevance`, `date_desc`, `date_asc`, `title_asc`, `title_desc`) to `FilterPanel`.
  - Added date range picker to `FilterPanel` and serialized request payload date range keys for compatibility.
  - Added exclude-keywords tags control to `FilterPanel` and wired it to `must_not_have`.
  - Updated `/media` search request wiring to include sort/date/exclude filters in payloads and query keys.
- Added targeted tests:
  - `apps/packages/ui/src/components/Review/__tests__/mediaSearchRequest.test.ts`
  - `apps/packages/ui/src/components/Media/__tests__/FilterPanel.test.tsx`
- Validation run:
  - `cd apps/packages/ui && bunx vitest run src/components/Review/__tests__/mediaSearchRequest.test.ts src/components/Media/__tests__/FilterPanel.test.tsx src/components/Media/__tests__/FilterChips.test.tsx`
  - Result: `3 passed` test files, `21 passed` tests.

- Completed Stage 2 implementation for findings `1.3`, `1.6`, `1.10`, and `1.12`:
  - Results list now displays compact relative ingest date badges (for example `2d ago`) next to media type badges.
  - Media types section now auto-expands when media types are available (before any manual user toggle).
  - Sidebar collapsed state is now persisted using extension storage key `media:sidebar:collapsed`.
  - Pagination now includes a page-size selector (`20`, `50`, `100`) wired to `results_per_page` request behavior.
- Added targeted Stage 2 tests:
  - `apps/packages/ui/src/components/Media/__tests__/ResultsList.test.tsx`
  - `apps/packages/ui/src/components/Media/__tests__/Pagination.test.tsx`
  - `apps/packages/ui/src/components/Media/__tests__/FilterPanel.test.tsx` (expanded with auto-expand behavior assertion)
- Validation run:
  - `cd apps/packages/ui && bunx vitest run src/components/Media/__tests__/FilterPanel.test.tsx src/components/Media/__tests__/ResultsList.test.tsx src/components/Media/__tests__/Pagination.test.tsx src/components/Review/__tests__/mediaSearchRequest.test.ts src/components/Media/__tests__/FilterChips.test.tsx`
  - Result: `5 passed` test files, `24 passed` tests.

- Completed Stage 3 implementation for findings `1.4` and `1.7`:
  - Added a small `?` search syntax help tooltip adjacent to the media search input.
  - Upgraded keyword suggestion loading strategy to prefer `/api/v1/media/keywords` and gracefully fallback to result-derived keywords if endpoint is missing/unavailable.
  - Added explicit helper copy in `FilterPanel` when fallback mode is active: suggestions are scoped to current results.
- Added targeted Stage 3 tests:
  - `apps/packages/ui/src/components/Media/__tests__/SearchBar.test.tsx`
  - `apps/packages/ui/src/components/Media/__tests__/FilterPanel.test.tsx` (expanded with result-scoped helper assertion)
- Validation run:
  - `cd apps/packages/ui && bunx vitest run src/components/Media/__tests__/SearchBar.test.tsx src/components/Media/__tests__/FilterPanel.test.tsx src/components/Media/__tests__/ResultsList.test.tsx src/components/Media/__tests__/Pagination.test.tsx src/components/Review/__tests__/mediaSearchRequest.test.ts src/components/Media/__tests__/FilterChips.test.tsx`
  - Result: `6 passed` test files, `27 passed` tests.

- Completed Stage 4 guardrails:
  - Added `JumpToNavigator` regression tests for threshold behavior (`<=5` hidden, overflow indicator) and `aria-pressed` selected-state semantics.
  - Revalidated existing `FilterChips` regression coverage to ensure remove/clear behaviors remain intact.
  - Added explicit media/notes tab toggle behavior to `ViewMediaPage` header with `aria-pressed` semantics and counts, then added helper-level regression tests for tab-state transitions.
- Added targeted Stage 4 tests:
  - `apps/packages/ui/src/components/Media/__tests__/JumpToNavigator.test.tsx`
  - `apps/packages/ui/src/components/Review/__tests__/mediaKinds.test.ts`
- Validation run:
  - `cd apps/packages/ui && bunx vitest run src/components/Review/__tests__/mediaKinds.test.ts src/components/Media/__tests__/JumpToNavigator.test.tsx src/components/Media/__tests__/SearchBar.test.tsx src/components/Media/__tests__/FilterPanel.test.tsx src/components/Media/__tests__/ResultsList.test.tsx src/components/Media/__tests__/Pagination.test.tsx src/components/Media/__tests__/FilterChips.test.tsx src/components/Review/__tests__/mediaSearchRequest.test.ts`
  - Result: `8 passed` test files, `34 passed` tests.
