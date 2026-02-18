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
**Status**: Not Started

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
**Status**: Not Started

## Stage 3: Safe Removal and Undo Pattern
**Goal**: Prevent accidental source loss during active research sessions.
**Success Criteria**:
- Source remove action uses undo toast with timeout and restore action.
- Optional confirm popover path is available for keyboard-only workflows.
- Undo behavior is consistent with other destructive actions in the workspace.
**Tests**:
- Component tests for remove -> undo -> restore flow.
- Integration test for timeout purge behavior after undo window expires.
**Status**: Not Started

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
**Status**: Not Started

## Dependencies

- Source status plumbing may require media ingest status endpoint/polling or event stream.
- Undo framework should align with global destructive-action handling in Category 9 plan.
