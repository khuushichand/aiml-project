# Implementation Plan: World Books - Error Handling and Edge Cases

## Scope

Components: Entry rendering strategy, import error UX, optimistic locking/version handling, delete-undo semantics, attachment consistency handling, recursive-scan safeguards.
Finding IDs: `10.1` through `10.6`

## Finding Coverage

- Performance edge cases for large entry sets: `10.1`
- Import diagnostics quality: `10.2`
- Concurrent edit safety: `10.3`
- Delete undo lifecycle expectations: `10.4`
- Attachment consistency and recursive scanning safeguards: `10.5`, `10.6`

## Stage 1: Resolve Large-Entry Rendering Failure Modes
**Goal**: Eliminate DOM scaling issues in high-volume world books.
**Success Criteria**:
- Implement virtualization or pagination with stable interaction semantics.
- Ensure API and UI expose `total` counts and current-window stats clearly.
- Keep filtering/search compatible with chosen rendering strategy.
**Tests**:
- Performance tests for 500-entry dataset interactions.
- Integration tests for filtering and selection behavior with windowed rendering.
- Regression tests for total-count accuracy.
**Status**: Complete

## Stage 2: Improve Import Error Diagnostics
**Goal**: Replace opaque parser output with actionable user guidance.
**Success Criteria**:
- Map parse/validation errors to clear messages for common cases.
- Preserve detailed raw error data in debug logs without exposing noisy details in primary UI.
- Keep backend validation detail visible in expandable `More details` section.
**Tests**:
- Unit tests for error classifier mapping.
- Integration tests for malformed JSON, missing fields, and zero-entry imports.
- UX tests for fallback message behavior when error shape is unknown.
**Status**: In Progress

## Stage 3: Add Optimistic Concurrency Handling
**Goal**: Prevent silent overwrites in concurrent edit scenarios.
**Success Criteria**:
- Include `version` in update payloads where backend supports expected-version semantics.
- Handle 409 conflict with clear message and guided recovery (reload and merge edits).
- Ensure stale edit attempts do not silently succeed or clobber fresh updates.
**Tests**:
- Integration tests simulating concurrent edits and conflict responses.
- Unit tests for update payload version propagation.
- Component tests for 409 conflict messaging and recovery action.
**Status**: Not Started

## Stage 4: Clarify Delete Undo Semantics and Pending State
**Goal**: Make delayed-delete behavior understandable and predictable.
**Success Criteria**:
- Add pending-deletion indicator while undo timer is active.
- Document navigation/refresh behavior for pending deletions in UI copy.
- Ensure timer cleanup on unmount does not produce confusing stale UI state.
**Tests**:
- Component tests for pending indicator lifecycle.
- Integration tests for undo timeout expiration and cancel behavior.
- Regression tests for route change/unmount cleanup behavior.
**Status**: Not Started

## Stage 5: Cover Attachment and Recursive Scanning Edge Warnings
**Goal**: Improve resilience for attachment churn and recursive-trigger surprises.
**Success Criteria**:
- Ensure stale attachment displays are reconciled immediately after character deletion events.
- Add warning banner when recursive scanning is enabled, including max depth note.
- Keep warning copy synchronized with backend recursion limit constant.
**Tests**:
- Integration tests for attachment refresh after character deletion/invalidation.
- Component tests for recursive warning visibility and dynamic max-depth text.
- Contract test confirming displayed max depth matches backend-configured limit.
**Status**: Not Started

## Dependencies

- Concurrency conflict UX depends on backend support for expected-version checks.
- Recursive depth display should consume a shared constant/config endpoint to avoid drift.
