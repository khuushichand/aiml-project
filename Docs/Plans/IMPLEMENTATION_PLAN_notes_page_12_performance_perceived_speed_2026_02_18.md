# Implementation Plan: Notes Page - Performance & Perceived Speed

## Scope

Components/pages: list/detail loading states, search request pacing, markdown preview rendering, long-running exports.
Finding IDs: `12.1` through `12.8`

## Finding Coverage

- Preserve current strengths (spinner, keepPreviousData, lazy modal): `12.1`, `12.2`, `12.8`
- Fill editor detail loading feedback gap: `12.3`
- Coordinate query pacing and debounce behavior: `12.5`
- Evaluate large-note preview performance: `12.6`
- Improve bulk-export progress visibility: `12.7`
- Preserve existing keyword debounce behavior: `12.4`

## Stage 1: Editor Detail Loading Feedback
**Goal**: Remove ambiguous idle periods during note-detail fetches.
**Success Criteria**:
- Render editor skeleton/spinner whenever `loadingDetail` is true.
- Keep previous content fallback behavior explicit to avoid confusion.
- Ensure loading indicators are non-blocking for already-cached content.
**Tests**:
- Component tests for loading skeleton visibility conditions.
- Integration tests for cached vs uncached note-detail transitions.
- Accessibility tests for loading status announcements.
**Status**: Not Started

## Stage 2: Query Efficiency and Refetch Control
**Goal**: Balance responsive search with controlled API load.
**Success Criteria**:
- Apply debounced query updates (300-500ms) for text search input.
- Preserve immediate response for explicit submit/search actions if added.
- Instrument client-side metrics for requests-per-query-session.
**Tests**:
- Unit tests for debounce cancellation and trailing invocation.
- Integration tests validating reduced network request volume.
- Telemetry contract tests for request metric emission.
**Status**: Not Started

## Stage 3: Large-Note Preview Performance Guardrails
**Goal**: Keep markdown preview usable for long notes.
**Success Criteria**:
- Introduce threshold-based lazy rendering/loading state for very large notes.
- Benchmark render times for representative 10K+ char notes.
- Document fallback behavior when thresholds are exceeded.
**Tests**:
- Performance tests for preview render time budgets.
- Regression tests for markdown feature parity under lazy path.
- Snapshot tests for loading placeholders in preview mode.
**Status**: Not Started

## Stage 4: Long-Running Export Progress UX
**Goal**: Increase trust during chunked bulk exports.
**Success Criteria**:
- Show in-flow progress indicator while export loops are running.
- Surface completion summary and any partial failures.
- Ensure UI remains interactive where safe (or clearly indicates temporary lock).
**Tests**:
- Integration tests for progress updates during chunked export.
- Failure-path tests for partial export errors and summary output.
- UX tests for warning visibility when max export thresholds are approached.
**Status**: Not Started

## Dependencies

- Search pacing changes should remain consistent with Plan 04 semantics.
- Export progress/failure messaging should align with Plans 07 and 13.
