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
**Status**: Not Started

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
**Status**: Not Started

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
**Status**: Not Started

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
**Status**: Not Started

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
**Status**: Not Started

## Dependencies

- Sorting and list counts should align with search/filter API semantics in Plan 04.
- Bulk operations should reuse export and delete safeguards from Plans 07 and 13.
