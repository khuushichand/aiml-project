# Implementation Plan: Media Pages - Information Gaps and Missing Functionality

## Scope

Pages/components: cross-cutting media capabilities currently unexposed in frontend (`/media`, `/media-multi`, detail panels, jobs/operations UI)
Finding IDs: `14.1` through `14.12`

## Finding Coverage

- Critical researcher workflows: `14.1`, `14.2`
- High-priority operational and interaction gaps: `14.3`, `14.4`, `14.5`, `14.6`, `14.7`, `14.8`, `14.9`
- Lower-priority but valuable expansion features: `14.10`, `14.11`, `14.12`

## Stage 1: Core Reading Continuity and Media Playback
**Goal**: Ship foundational reading/review capabilities needed for daily researcher use.
**Success Criteria**:
- Reading progress API is fully integrated (save/restore/clear) with visible progress indicator.
- Embedded audio/video playback added where original files exist.
- Progress and playback behavior are resilient across navigation and reload.
**Tests**:
- Integration tests for progress persistence and restoration.
- Component tests for player rendering and seek behavior.
- Regression tests for content rendering when no original file exists.
**Status**: Complete

## Stage 2: Document Intelligence Panel Suite
**Goal**: Expose the platform's built backend intelligence endpoints in UI.
**Success Criteria**:
- Outline, insights, references, figures, and annotations-related intelligence panels are available from media detail view.
- Panel loading/error/empty states are standardized and non-blocking.
- Users can navigate intelligence outputs without losing reading context.
**Tests**:
- Integration tests for each document intelligence endpoint binding.
- Component tests for panel tabs/sections and fallback states.
- Regression tests for detail page performance with intelligence panels present.
**Status**: Complete

## Stage 3: Library-Scale Operations and Job Visibility
**Goal**: Enable efficient management of many media items.
**Success Criteria**:
- Main list multi-select mode and bulk actions implemented (tag/delete/export baseline).
- Export modal supports JSON/Markdown/plain text outputs.
- Reprocess action exposed in content viewer menu.
- Ingestion/reprocessing job tracker UI added with lifecycle visibility.
**Tests**:
- Integration tests for bulk selection and action execution.
- Component tests for export format selection and payload generation.
- Integration tests for reprocess action and job status updates.
**Status**: Complete
**Progress Notes (2026-02-18)**:
- Completed: export modal/action in `ContentViewer` with JSON/Markdown/plain text support and regression tests.
- Completed: reprocess action in `ContentViewer` menu with success/error coverage.
- Completed: ingest job tracker panel integrated into `/media` sidebar with batch ID input, refresh/auto-refresh, status rendering, and retry coverage.
- Completed: main list multi-select mode and bulk action toolbar baseline (`tag/delete/export`) with regression coverage.

## Stage 4: Research Workflow Organization and Annotation
**Goal**: Support researcher organization and annotation-first reading workflows.
**Success Criteria**:
- Annotation/highlighting UI layer and sidebar implemented with backend CRUD/sync.
- Collection/folder-like organization strategy delivered (client-side collections or backend-backed grouping).
- Annotation and organization state interoperates with search/filter and multi-item review.
**Tests**:
- Integration tests for annotation create/edit/delete/sync flows.
- Component tests for collection creation, assignment, and filtering.
- Regression tests for existing keyword/tag workflows.
**Status**: Complete
**Progress Notes (2026-02-18)**:
- Added annotation authoring controls in `ContentViewer` intelligence annotations tab:
  create from selection/manual text, edit note, delete, and sync-now actions.
- Added client-side media collections in `/media` with storage-backed persistence.
- Integrated collection filter into sidebar search/filter flow and added multi-review handoff for active collection or bulk selection.
- Added regression coverage for annotation CRUD/sync, selection-to-annotation highlight creation, and collection bulk workflows.
- Added collection assignment/merge and collection-filter scoped keyword-tagging tests to preserve existing tagging behavior under organization filters.

## Stage 5: Extended Insights and Academic Integrations
**Goal**: Add lower-priority expansion features after core workflows are stable.
**Success Criteria**:
- Content statistics dashboard available at library level.
- Citation manager export/integration path defined and implemented (for example BibTeX-compatible output).
- Scheduled re-ingestion controls available for refreshable URL sources.
**Tests**:
- Integration tests for stats aggregation and rendering.
- Export contract tests for citation data format.
- Scheduler/job tests for recurring re-ingestion setup and status reporting.
**Status**: In Progress
**Progress Notes (2026-02-18)**:
- Added `MediaLibraryStatsPanel` to `/media` with:
  visible/total counts, visible word-count aggregation, top media-type distribution, and storage usage summary.
- Wired storage usage to backend `GET /api/v1/storage/usage` in `ViewMediaPage` with loading and error states.
- Added regression coverage in `MediaLibraryStatsPanel.test.tsx` for metric rendering and storage loading/error states.
- Added `BibTeX` export format in `ContentViewer` export modal, deriving citation fields from `safe_metadata` (DOI, authors, journal, year, URL).
- Added export regression coverage to validate `.bib` output payload generation.

## Dependencies

- Stage 1 should share implementations with Category 3 (`3.4`, `3.9`).
- Stage 3 depends on jobs/scheduler UX conventions used elsewhere in the app.
- Stage 4 annotation UX should align with accessibility requirements in Category 15.
