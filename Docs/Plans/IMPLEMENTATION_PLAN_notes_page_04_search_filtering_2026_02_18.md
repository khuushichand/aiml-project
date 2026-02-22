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
**Status**: Complete

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
**Status**: Complete

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
**Status**: Complete

## Dependencies

- Search UI changes feed list rendering and metadata decisions in Plan 01.
- Highlighting behavior should remain compatible with graph/backlink rendering plans (05/06).

## Progress Notes (2026-02-18)

- Completed Stage 1 in `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`:
  - Updated search placeholder copy to explicitly communicate full-text behavior.
  - Added inline helper text documenting title/content search scope and `text + keywords` AND semantics.
  - Implemented 350ms debounce for query-to-fetch updates while preserving immediate Enter submission.
- Added Stage 1 verification in `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage11.search-filtering.test.tsx`:
  - Verifies semantic helper text visibility and updated placeholder copy.
  - Verifies debounce cancellation during rapid typing and single final query issuance.
- Completed Stage 2 in `/apps/packages/ui/src/components/Notes/NotesListPanel.tsx` and `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`:
  - Added frontend fallback term highlighting for titles/previews in note list results.
  - Added Search Tips popover documenting phrase/prefix usage and AND semantics.
  - Wired active search query into list-panel highlighting flow.
- Added Stage 2 verification in:
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesListPanel.stage2.search-highlighting.test.tsx`
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage11.search-filtering.test.tsx`
  - Verifies phrase/token highlighting and Search Tips content visibility.
- Completed Stage 3 in `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`:
  - Added a Recent Notes section in the sidebar with persisted, deduplicated last-opened entries.
  - Added explicit in-note search guidance in the main search area and Search Tips popover.
  - Wired recent-note capture into note-detail load flow for stable ordering and quick re-open.
- Added Stage 3 verification in `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage12.recent-notes.test.tsx`:
  - Verifies recent note ordering and persistence.
  - Verifies persisted recent notes load and Ctrl/Cmd+F guidance visibility.
- Added in-note search scope decision record:
  - `/Docs/Plans/DECISION_RECORD_notes_search_in_note_scope_stage3_2026_02_18.md`
