# Implementation Plan: Notes Page - Notes List & Navigation

## Scope

Components/pages: `/notes` sidebar list, filter controls, pagination and list item metadata in `NotesManagerPage.tsx` and `NotesListPanel.tsx`.
Finding IDs: `1.1` through `1.11`

## Finding Coverage

- Search/filter clarity and active-state context: `1.2`, `1.4`
- List ordering, preview density, page-size controls: `1.1`, `1.5`, `1.11`
- Scannability metadata and keyword frequency signals: `1.3`, `1.6`
- Multi-note workflows and list scalability: `1.7`, `1.10`
- Preserve strengths: `1.8`, `1.9`

## Stage 1: Filter and Search Discoverability
**Goal**: Make list filtering behavior explicit and visible at all times.
**Success Criteria**:
- Search input copy explicitly states title+content full-text coverage.
- Add active-filter summary bar showing note counts and current query/token filters.
- Keep existing clear-filters action while surfacing state in plain language.
**Tests**:
- Component tests for summary rendering across empty, query-only, keyword-only, and combined states.
- Accessibility test validating summary announcement and control labeling.
- Integration test ensuring filter summary reflects server response counts.
**Status**: Complete

## Stage 2: Sorting, Preview, and Pagination Controls
**Goal**: Improve note triage speed in medium and large collections.
**Success Criteria**:
- Add sort selector with `modified desc`, `created desc`, `title asc`, `title desc` options.
- Expand preview strategy to either 120-150 chars or first non-title line extraction.
- Enable page-size switcher (20/50/100) with persisted user preference.
**Tests**:
- Integration tests for each sort option against expected API params and ordering.
- Component tests for preview fallback behavior.
- Persistence test for page-size preference across reload.
**Status**: Complete

## Stage 3: At-a-Glance Metadata Badges
**Goal**: Improve scanning with compact visual indicators.
**Success Criteria**:
- Add icon/badge indicators for keywords, backlinks, and recently edited notes.
- Show per-keyword note counts in filter dropdown and browse-keywords modal.
- Preserve current selected-note styling contract.
**Tests**:
- Component tests for icon/badge visibility by note metadata state.
- Contract tests for keyword count formatting and zero-count behavior.
- Visual regression tests to prevent row-density regressions.
**Status**: Complete

## Stage 4: Bulk Selection and Operations Baseline
**Goal**: Introduce safe multi-note management workflows.
**Success Criteria**:
- Support checkbox or modifier-key multi-selection.
- Provide bulk operations scaffold (delete/export/keyword assignment) with guarded confirmation.
- Expose bulk-selection count and clear-selection affordance.
**Tests**:
- Integration tests for keyboard/mouse multi-select semantics.
- Action tests for bulk delete/export dispatch and confirmation paths.
- Accessibility tests for multi-select state announcements.
**Status**: Complete

## Stage 5: Scalable List Rendering Option
**Goal**: Preserve responsiveness for large note collections.
**Success Criteria**:
- Evaluate and optionally ship virtualized list or load-more pattern for 100+ notes.
- Maintain existing pagination fallback if virtualization is deferred.
- Document decision and performance threshold trigger.
**Tests**:
- Performance test with 500+ mock notes.
- Regression test for selection/filter behavior under chosen rendering strategy.
- Decision record linked in plan/docs.
**Status**: Complete

## Dependencies

- Sorting and list counts should align with search/filter API semantics in Plan 04.
- Bulk operations should reuse export and delete safeguards from Plans 07 and 13.

## Progress Notes (2026-02-18)

- Completed Stage 1 in `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`:
  - Preserved explicit full-text search copy (`Search titles & content...`) and helper semantics.
  - Added an active-filter summary live region showing `Showing X of Y notes` plus current query/keyword criteria.
  - Preserved and accessibility-labeled the existing clear-filters action.
- Added Stage 1 verification in `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage13.navigation-filter-summary.test.tsx`:
  - Covers query-only, keyword-only, and combined filter summary rendering.
  - Verifies live-region semantics (`role="status"`, `aria-live="polite"`).
  - Verifies clear-filter control labeling and count consistency from search API totals.
- Completed Stage 2 in:
  - `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
  - `/apps/packages/ui/src/components/Notes/NotesListPanel.tsx`
  - `/apps/packages/ui/src/services/settings/ui-settings.ts`
  - Added sortable list controls (`modified desc`, `created desc`, `title asc`, `title desc`) with API query params plus frontend fallback ordering.
  - Added page-size switcher (`20/50/100`) in pagination and persisted page-size preference (`tldw:notesPageSize`).
  - Updated preview strategy to prefer the first non-title content line and expanded preview length to 140 chars.
- Added Stage 2 verification in:
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage14.sorting-pagination.test.tsx`
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesListPanel.stage14.preview-strategy.test.tsx`
  - Verifies sort-option API params and rendered ordering, page-size persistence/rehydration, and preview fallback behavior.
- Completed Stage 3 in:
  - `/apps/packages/ui/src/components/Notes/NotesListPanel.tsx`
  - `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
  - `/apps/packages/ui/src/components/Notes/KeywordPickerModal.tsx`
  - `/apps/packages/ui/src/services/note-keywords.ts`
  - `/tldw_Server_API/app/api/v1/endpoints/notes.py`
  - `/tldw_Server_API/app/api/v1/schemas/notes_schemas.py`
  - `/tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
  - Added list-row badges (keywords, backlink, edited-within-24h) for scanability.
  - Added keyword note-count labels in filter dropdown and Browse Keywords modal.
  - Added backend `include_note_counts` support on keywords list API plus DB aggregation helper.
- Added Stage 3 verification in:
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesListPanel.stage15.metadata-badges.test.tsx`
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage15.keyword-counts.test.tsx`
  - `/tldw_Server_API/tests/Notes_NEW/integration/test_notes_api.py::test_keywords_list_can_include_note_counts`
  - Frontend suite passes; backend pytest execution is blocked in current environment by missing `httpx` test dependency.
- Completed Stage 4 in:
  - `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
  - `/apps/packages/ui/src/components/Notes/NotesListPanel.tsx`
  - Added checkbox-based multi-selection with shift-range behavior on visible notes.
  - Added bulk actions bar with selected-count status, clear-selection, bulk export, bulk delete, and bulk keyword assignment scaffold.
  - Added guarded confirmation flows for destructive and write actions before dispatch.
- Added Stage 4 verification in:
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesListPanel.stage16.bulk-selection.test.tsx`
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage16.bulk-actions.test.tsx`
  - Full Notes UI regression suite passed (`24 files, 61 tests`), including all prior stage tests.
- Completed Stage 5 in:
  - `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
  - Added large-list threshold hint (`total >= 100`) to make pagination fallback explicit.
  - Kept server-side pagination as the primary rendering strategy for this cycle.
- Added Stage 5 verification in:
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage17.scalability-hint.test.tsx`
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesListPanel.stage17.large-list.test.tsx`
  - Added large-list regression coverage with 500+ mock notes and verified bulk-selection behavior remains intact.
- Added Stage 5 decision record:
  - `/Docs/Plans/DECISION_RECORD_notes_list_scalability_stage5_2026_02_18.md`
  - Documents why virtualization/load-more is deferred and defines trigger thresholds for revisit.
