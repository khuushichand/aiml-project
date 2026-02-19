# Implementation Plan: Media Pages - Search Experience

## Scope

Pages/components: `/media` search query flow (`ViewMediaPage.tsx`, `ResultsList.tsx`, advanced search controls)
Finding IDs: `2.1` through `2.8`

## Finding Coverage

- Preserve strong baseline behavior: `2.1`, `2.4`
- Immediate usability upgrades: `2.2`, `2.3`
- Advanced search capability exposure: `2.5`, `2.6`, `2.7`, `2.8`

## Stage 1: Relevance Visibility and No-Results Recovery
**Goal**: Make search outcomes easier to interpret and recover from.
**Success Criteria**:
- Snippets support term highlighting via a shared `highlightMatches()` utility.
- No-results views provide actionable suggestions (broaden query, remove filters, ingest content).
- Highlighting is safe for escaped content and does not break existing snippet rendering.
**Tests**:
- Unit tests for highlight utility tokenization and escaping.
- Component tests for highlighted snippet rendering.
- Integration tests for both no-results states and contextual guidance actions.
**Status**: Complete

## Stage 2: Advanced Query Controls
**Goal**: Expose structured power-user controls without degrading default simplicity.
**Success Criteria**:
- Advanced panel includes exact phrase input wired to `exact_phrase`.
- Search-scope field toggles added for title/content.
- Optional relevance boost controls added (or hidden behind power-user section) using `boost_fields`.
**Tests**:
- Component tests for advanced panel state and serialization.
- Integration tests for payloads when advanced controls are toggled.
- Regression test ensuring default query path remains unchanged when controls are unused.
**Status**: Complete

## Stage 3: Metadata Search Mode
**Goal**: Enable researcher-focused metadata retrieval from existing backend capabilities.
**Success Criteria**:
- Metadata search mode implemented (DOI, PMID, journal, license, operator support as applicable).
- UI clearly separates full-text vs metadata search to avoid ambiguous behavior.
- Response rendering supports metadata-driven results without losing standard filters.
**Tests**:
- Integration tests for metadata query fields and operator serialization.
- End-to-end flow test for DOI/PMID lookup.
- Error-state tests for invalid metadata operator combinations.
**Status**: Complete

## Stage 4: Baseline Regression and Responsiveness Guardrails
**Goal**: Protect existing responsive search interactions while expanding functionality.
**Success Criteria**:
- 300ms debounce remains in place unless explicitly configured otherwise.
- Filter + query interaction remains synchronized.
- New advanced controls do not introduce excessive request churn.
**Tests**:
- Debounce timing unit/integration test.
- Search request count test under rapid typing with filters enabled.
- Existing filter interaction regression tests.
**Status**: Complete

## Dependencies

- Stage 2 and Stage 3 should reuse sort/date controls from Category 1 where possible.

## Progress Notes (2026-02-18)

- Completed Stage 1 implementation for findings `2.2` and `2.3`:
  - Added shared snippet-highlighting utility at `apps/packages/ui/src/components/Media/highlightMatches.tsx` with safe tokenization for quoted phrases/operators and regex-escaping.
  - Wired snippet highlighting into `ResultsList` so query matches render with `<mark>` in result snippets.
  - Expanded no-results states to include actionable guidance:
    - Broaden search (clear search action),
    - Remove filters (clear filters action),
    - Ingest content (open quick-ingest action).
  - Hooked `ViewMediaPage` to pass search query and empty-state actions into `ResultsList`.
- Added targeted Stage 1 tests:
  - `apps/packages/ui/src/components/Media/__tests__/highlightMatches.test.tsx`
  - `apps/packages/ui/src/components/Media/__tests__/ResultsList.test.tsx` (expanded coverage)
- Validation run:
  - `cd apps/packages/ui && bunx vitest run src/components/Media/__tests__/highlightMatches.test.tsx src/components/Media/__tests__/ResultsList.test.tsx src/components/Media/__tests__/FilterPanel.test.tsx src/components/Review/__tests__/mediaSearchRequest.test.ts`
  - Result: `4 passed` test files, `14 passed` tests.

- Completed Stage 2 implementation for findings `2.5`, `2.7`, and `2.8`:
  - Added an `Advanced search` section to `FilterPanel` with:
    - exact phrase input (`exact_phrase`),
    - search scope toggles for title/content (`fields`),
    - optional relevance boost controls for title/content (`boost_fields`).
  - Extended media search payload builder and filter detection logic to support advanced fields while preserving default behavior when unused.
  - Wired advanced state from `ViewMediaPage` into search payload/query keys/refetch dependencies and clear-all/reset flows.
- Added/expanded Stage 2 tests:
  - `apps/packages/ui/src/components/Media/__tests__/FilterPanel.test.tsx` (advanced controls + clear-all reset coverage)
  - `apps/packages/ui/src/components/Review/__tests__/mediaSearchRequest.test.ts` (advanced payload serialization + default-path regression checks)
- Validation run:
  - `cd apps/packages/ui && bunx vitest run src/components/Review/__tests__/mediaSearchRequest.test.ts src/components/Media/__tests__/FilterPanel.test.tsx src/components/Media/__tests__/ResultsList.test.tsx src/components/Media/__tests__/highlightMatches.test.tsx`
  - Result: `4 passed` test files, `16 passed` tests.

- Completed Stage 3 implementation for finding `2.6`:
  - Added explicit `Search mode` toggle (`Full-text` vs `Metadata`) in `FilterPanel` to clearly separate behaviors.
  - Implemented metadata search controls with field/operator/value filters and match mode (`all`/`any`) for DOI, PMID, PMCID, arXiv ID, S2 Paper ID, journal, and license.
  - Wired metadata mode in `ViewMediaPage` to call `GET /api/v1/media/metadata-search` via a structured path builder and map safe-metadata results into existing result rendering.
  - Preserved standard browsing controls in metadata mode via client-side filtering/sorting (media type, date range, include/exclude keywords, query text, title/date sorting).
  - Added validation/error handling for invalid operator combinations on identifier fields (e.g., DOI requires `eq`).
- Added Stage 3 helper/tests:
  - `apps/packages/ui/src/components/Review/mediaMetadataSearchRequest.ts`
  - `apps/packages/ui/src/components/Review/__tests__/mediaMetadataSearchRequest.test.ts`
  - Expanded `apps/packages/ui/src/components/Media/__tests__/FilterPanel.test.tsx` for metadata-mode controls and validation display.
- Validation runs:
  - `cd apps/packages/ui && bunx vitest run src/components/Review/__tests__/mediaMetadataSearchRequest.test.ts src/components/Review/__tests__/mediaSearchRequest.test.ts src/components/Media/__tests__/FilterPanel.test.tsx src/components/Media/__tests__/ResultsList.test.tsx src/components/Media/__tests__/highlightMatches.test.tsx`
  - Result: `5 passed` test files, `22 passed` tests.
  - `cd apps/packages/ui && bunx vitest run src/components/Review/__tests__/mediaKinds.test.ts src/components/Review/__tests__/mediaSearchRequest.test.ts src/components/Review/__tests__/mediaMetadataSearchRequest.test.ts src/components/Media/__tests__/highlightMatches.test.tsx src/components/Media/__tests__/FilterChips.test.tsx src/components/Media/__tests__/Pagination.test.tsx src/components/Media/__tests__/JumpToNavigator.test.tsx src/components/Media/__tests__/SearchBar.test.tsx src/components/Media/__tests__/ResultsList.test.tsx src/components/Media/__tests__/FilterPanel.test.tsx`
  - Result: `10 passed` test files, `48 passed` tests.

- Completed Stage 4 guardrails:
  - Replaced ad-hoc debounce state handling in `ViewMediaPage` with shared `useDebounce(query, 300)` to preserve and centralize the 300ms threshold.
  - Removed redundant immediate `refetch()` calls from filter-control callbacks and relied on state-driven effects to reduce duplicate request churn.
  - Updated debounced-query and filter-change refetch effects to avoid double-fetches when transitioning from non-page-1 states (reset page first, then refetch on settled state).
- Added/expanded Stage 4 tests:
  - `apps/packages/ui/src/hooks/__tests__/useDebounce.test.tsx` (timing + rapid-input coalescing behavior)
  - Regression test suite re-run for media search/filter components.
- Validation runs:
  - `cd apps/packages/ui && bunx vitest run src/hooks/__tests__/useDebounce.test.tsx src/components/Review/__tests__/mediaMetadataSearchRequest.test.ts src/components/Review/__tests__/mediaSearchRequest.test.ts src/components/Media/__tests__/FilterPanel.test.tsx src/components/Media/__tests__/ResultsList.test.tsx src/components/Media/__tests__/highlightMatches.test.tsx`
  - Result: `6 passed` test files, `24 passed` tests.
  - `cd apps/packages/ui && bunx vitest run src/hooks/__tests__/useDebounce.test.tsx src/components/Review/__tests__/mediaKinds.test.ts src/components/Review/__tests__/mediaSearchRequest.test.ts src/components/Review/__tests__/mediaMetadataSearchRequest.test.ts src/components/Media/__tests__/highlightMatches.test.tsx src/components/Media/__tests__/FilterChips.test.tsx src/components/Media/__tests__/Pagination.test.tsx src/components/Media/__tests__/JumpToNavigator.test.tsx src/components/Media/__tests__/SearchBar.test.tsx src/components/Media/__tests__/ResultsList.test.tsx src/components/Media/__tests__/FilterPanel.test.tsx`
  - Result: `11 passed` test files, `50 passed` tests.
