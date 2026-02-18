# Implementation Plan: Notes Page - Search & Filtering

## Scope

Components/pages: `/notes` search input and query lifecycle, filter composition behavior, search results rendering.
Finding IDs: `4.1` through `4.7`

## Finding Coverage

- Full-text capability discoverability: `4.1`
- Result readability and query education: `4.2`, `4.4`
- Preserve and document AND semantics: `4.3`
- Optional advanced convenience features: `4.5`, `4.6`
- Query pacing/performance: `4.7`

## Stage 1: Search Semantics Clarity and Input Debounce
**Goal**: Set correct mental model while reducing request churn.
**Success Criteria**:
- Update placeholder/help text to explicitly state title+content full-text behavior.
- Add 300-500ms debounce to query updates before triggering fetches.
- Document `query AND keyword` semantics in compact inline helper copy.
**Tests**:
- Unit tests for debounce timing and cancellation on rapid typing.
- Integration tests validating query issuance count reduction.
- UX copy tests verifying semantic helper visibility.
**Status**: Not Started

## Stage 2: Match Highlighting and Search Tips
**Goal**: Improve scan speed in result lists.
**Success Criteria**:
- Add term highlighting in title/preview snippets.
- Implement backend snippet response or frontend fallback highlighting strategy.
- Provide a searchable tips popover for phrase and operator usage.
**Tests**:
- Integration tests for highlighted matches on single and multi-term queries.
- Backend/API tests if snippet fragments are server-generated.
- Accessibility tests for highlighted text contrast and screen-reader output.
**Status**: Not Started

## Stage 3: Quick Access and Advanced Discovery Extensions
**Goal**: Provide navigation shortcuts without disrupting core flow.
**Success Criteria**:
- Add recent-notes section with last-opened entries.
- Validate scope decision for in-note search (defer vs implement).
- Keep browser-native Ctrl+F guidance if in-note search is deferred.
**Tests**:
- Component tests for recent section ordering and empty state.
- Persistence tests for last-opened note tracking.
- Decision record for in-note search scope and constraints.
**Status**: Not Started

## Dependencies

- Search UI changes feed list rendering and metadata decisions in Plan 01.
- Highlighting behavior should remain compatible with graph/backlink rendering plans (05/06).
