# Implementation Plan: Workspace Playground - Source Management

## Scope

Components: `SourcesPane`, `AddSourceModal`, related source store/actions in `WorkspacePlayground`
Finding IDs: `1.1` through `1.12`

## Finding Coverage

- Ingestion feedback and safety: `1.2`, `1.3`, `1.8`, `1.10`
- Intake efficiency and relevance preview: `1.1`, `1.4`, `1.5`, `1.6`, `1.9`
- Destructive action safety: `1.7`
- List scalability and organization: `1.11`, `1.12`

## Stage 1: Ingestion Feedback and Safety
**Goal**: Make source ingestion transparent, bounded, and recoverable.
**Success Criteria**:
- Upload flow shows per-file progress (or spinner fallback when byte progress is unavailable).
- `beforeUpload` enforces max size (default 500 MB, configurable).
- Oversized/unsupported files are rejected with actionable messages.
- `WorkspaceSource` includes lifecycle status (`processing`, `ready`, `error`) and status renders in list.
- Processing sources are visibly disabled for RAG selection until ready.
- Error mapping exists for common HTTP/network failures with user-readable guidance.
**Tests**:
- Unit tests for size validation and error-to-message mapper.
- Component tests for per-file progress rendering and status badges.
- Integration test for upload -> `processing` -> `ready` transitions.
- Integration test for unsupported file and oversized file rejection messaging.
**Status**: Complete

## Stage 2: Faster Source Intake and Relevance Preview
**Goal**: Reduce time-to-ingest for recurring and batch workflows.
**Success Criteria**:
- Add Source tabs reorder to `Upload > Library > URL > Paste > Search`.
- URL tab supports single and batch input modes (`one URL per line`).
- Batch add returns per-URL status results.
- Search result items render snippet/content preview and favicon when available.
- Library tab supports pagination/load-more and shows total count.
- Source metadata (`fileSize`, `duration`, `pageCount`, `createdAt`) is populated from API and surfaced via tooltip/expander.
**Tests**:
- Component test for tab ordering.
- Unit/integration tests for URL parser and per-URL status reporting.
- Component test for snippet rendering fallback logic.
- Integration test for library paging and count text.
- Unit test ensuring metadata normalization from API response.
**Status**: Complete

## Stage 3: Safe Removal and Undo Pattern
**Goal**: Prevent accidental source loss during active research sessions.
**Success Criteria**:
- Source remove action uses undo toast with timeout and restore action.
- Optional confirm popover path is available for keyboard-only workflows.
- Undo behavior is consistent with other destructive actions in the workspace.
**Tests**:
- Component tests for remove -> undo -> restore flow.
- Integration test for timeout purge behavior after undo window expires.
**Status**: Complete

## Stage 4: Large-List Performance and Source Organization
**Goal**: Keep Sources pane responsive and organized with large collections.
**Success Criteria**:
- Source list virtualization enabled above defined threshold.
- Drag-and-drop source reordering persists order in workspace state.
- Keyboard-accessible reorder affordances are provided.
**Tests**:
- Component/perf test for rendering 200+ sources without scroll jank.
- Integration test for reorder persistence after reload.
- Accessibility test for keyboard reorder controls.
**Status**: Complete

## Dependencies

- Source status plumbing may require media ingest status endpoint/polling or event stream.
- Undo framework should align with global destructive-action handling in Category 9 plan.

## Progress Notes (2026-02-18)

- Stage 1 completed:
  - Added source-ingestion utility helpers for:
    - upload max-size resolution (default 500 MB, env override support),
    - file-type and size validation before upload starts,
    - user-friendly error mapping for common HTTP/network failure classes.
  - Upgraded Upload tab with per-file progress-state rows:
    - per-file `Uploading` spinner fallback when byte progress is unavailable,
    - per-file `Processing` state after successful upload handoff,
    - per-file error rows for rejected or failed uploads.
  - Added explicit upload limit guidance in UI hint text (`Max {{limit}} per file`).
  - Wired mapped actionable errors into URL, Paste, Search, and Library ingestion paths.
  - Verified status lifecycle behavior remains consistent with existing source readiness gating:
    - newly uploaded sources are created as `processing`,
    - non-ready sources stay disabled in source selection,
    - workspace polling promotes `processing -> ready` and marks repeated failures as `error`.

- Stage 1 files updated:
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/SourcesPane/AddSourceModal.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/SourcesPane/source-ingestion-utils.ts`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/AddSourceModal.stage1.ingestion.test.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/source-ingestion-utils.test.ts`

- Stage 1 validation:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/WorkspacePlayground/__tests__/source-ingestion-utils.test.ts src/components/Option/WorkspacePlayground/__tests__/AddSourceModal.stage1.mobile.test.tsx src/components/Option/WorkspacePlayground/__tests__/AddSourceModal.stage1.ingestion.test.tsx src/components/Option/WorkspacePlayground/__tests__/AddSourceModal.stage9.error.test.tsx src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage2.test.tsx src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage3.test.tsx --reporter=verbose`

- Stage 2 completed:
  - Reordered Add Source tabs to `Upload -> Library -> URL -> Paste -> Search`.
  - Added URL intake modes:
    - Single URL input,
    - Batch URL textarea (`one URL per line`) with duplicate-line filtering.
  - Implemented per-URL batch status reporting in URL tab with per-row success/error outcomes and summary error reporting on partial failures.
  - Added search result relevance preview:
    - snippet/content two-line preview,
    - favicon rendering derived from result hostname.
  - Added library paging affordances:
    - `Load more` pagination,
    - total visibility text (`Showing X of Y`),
    - page-aware fetching while preserving cache for page-1 default library load.
  - Added source metadata normalization and propagation from media API responses (`url`, `fileSize`, `duration`, `pageCount`, `thumbnailUrl`) across upload/url/search/library ingestion flows.
  - Surfaced source metadata in Sources pane via compact metadata preview + tooltip.

- Stage 2 files updated:
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/SourcesPane/AddSourceModal.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/SourcesPane/index.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/AddSourceModal.stage2.intake.test.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage2.test.tsx`

- Stage 2 validation:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/WorkspacePlayground/__tests__/AddSourceModal.stage1.ingestion.test.tsx src/components/Option/WorkspacePlayground/__tests__/AddSourceModal.stage1.mobile.test.tsx src/components/Option/WorkspacePlayground/__tests__/AddSourceModal.stage2.intake.test.tsx src/components/Option/WorkspacePlayground/__tests__/AddSourceModal.stage3.performance.test.tsx src/components/Option/WorkspacePlayground/__tests__/AddSourceModal.stage9.error.test.tsx src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage2.test.tsx src/components/Option/WorkspacePlayground/__tests__/source-ingestion-utils.test.ts --reporter=verbose`

- Stage 3 completed:
  - Preserved undo-first source deletion behavior (toast + timed undo restore path).
  - Added keyboard-focused confirm path for source deletion using `Popconfirm`:
    - keyboard activation (`Enter` / `Space`) opens confirmation,
    - confirmation executes the same undo-backed removal flow for consistency.
  - Added regression test coverage ensuring keyboard users can opt into confirmation before removal.

- Stage 3 files updated:
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/SourcesPane/index.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage2.test.tsx`

- Stage 3 validation:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage2.test.tsx src/components/Option/WorkspacePlayground/__tests__/AddSourceModal.stage2.intake.test.tsx --reporter=verbose`

- Stage 4 completed:
  - Extended workspace source store with explicit `reorderSource(sourceId, targetIndex)` action.
  - Implemented drag-and-drop source reordering in `SourcesPane`:
    - drag-over/drop reorder within source list,
    - preserved existing source drag payload for cross-pane chat interactions.
  - Added keyboard-accessible source reordering controls (`Move up` / `Move down`) per row.
  - Verified source ordering persistence through store rehydration.
  - Existing virtualization behavior retained and covered by regression tests for large lists.

- Stage 4 files updated:
  - `apps/packages/ui/src/store/workspace.ts`
  - `apps/packages/ui/src/store/__tests__/workspace.test.ts`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/SourcesPane/index.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage2.test.tsx`

- Stage 4 validation:
  - `cd apps/packages/ui && bunx vitest run src/store/__tests__/workspace.test.ts src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage2.test.tsx src/components/Option/WorkspacePlayground/__tests__/AddSourceModal.stage2.intake.test.tsx --reporter=verbose`
