# Implementation Plan: Media Pages - Error Handling and Edge Cases

## Scope

Pages/components: media detail fetch lifecycle, stale-item handling, delete recovery UX, multi-page error reporting
Finding IDs: `13.1` through `13.7`

## Finding Coverage

- Preserve strong existing resilience: `13.1`, `13.3`, `13.6`, `13.7`
- Add visible detail-fetch recovery UX: `13.2`
- Improve stale-data reconciliation: `13.4`
- Add immediate undo path for delete: `13.5`

## Stage 1: Visible Detail Fetch Error States
**Goal**: Replace silent failures with actionable content-area errors.
**Success Criteria**:
- Content area shows explicit inline error when detail fetch fails.
- Retry control re-attempts fetch and clears stale display state.
- Previous-item stale content is not shown as if it were current item content.
**Tests**:
- Integration tests for failed detail fetch -> inline error -> retry success.
- Component tests for error-state rendering and reset behavior.
- Regression tests for normal detail load transitions.
**Status**: Complete

## Stage 2: Stale Item Detection and Reconciliation
**Goal**: Detect items deleted/changed by other clients and recover gracefully.
**Success Criteria**:
- Stale item checks added (polling, ETag, or conditional fetch strategy).
- UI communicates when current item is no longer available.
- Selection/list state reconciles automatically after stale detection.
**Tests**:
- Integration tests simulating cross-client delete/update.
- Contract tests for ETag/conditional request handling (if implemented).
- Regression tests for normal navigation without stale events.
**Status**: Complete

## Stage 3: Undo Delete Consistency and Regression Hardening
**Goal**: Standardize immediate recovery and protect existing robust error paths.
**Success Criteria**:
- Undo toast added after soft-delete and integrated with restore API.
- Existing offline handling, sanitization, multi-review partial failure, and trash partial failure behavior remains unchanged.
- Error messages remain actionable and non-leaky.
**Tests**:
- Integration tests for soft-delete undo flow.
- Regression tests for offline and partial-failure scenarios.
- Snapshot tests for consolidated error and retry messaging.
**Status**: Complete

## Dependencies

- Undo flow should reuse implementation from Category 8 (`8.7`).
