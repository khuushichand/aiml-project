# Implementation Plan: Workspace Playground - Error Handling and Edge Cases

## Scope

Components: Add Source batch flow, workspace root container, store persistence, generation rehydration, destructive actions
Finding IDs: `9.1` through `9.7`

## Finding Coverage

- Keep positive behavior with better copy: `9.1`
- Error visibility and recovery: `9.2`, `9.3`, `9.4`
- State consistency across sessions/tabs: `9.5`, `9.6`
- Reversible destructive actions: `9.7`

## Stage 1: Actionable Error Surfaces
**Goal**: Replace silent or opaque failures with explicit, recoverable messaging.
**Success Criteria**:
- Batch URL ingestion reports per-item success/failure summary.
- Workspace-level error boundary captures render crashes with reload action.
- Empty-state copy clarifies general chat is available without sources.
**Tests**:
- Integration test for mixed-result batch URL add summary output.
- Component test for error boundary fallback and retry.
- Copy regression test for empty state messaging.
**Status**: Not Started

## Stage 2: Persistence Failure and Cross-Tab Resilience
**Goal**: Prevent silent persistence failures and stale-tab overwrite surprises.
**Success Criteria**:
- `QuotaExceededError` handling warns user with remediation guidance.
- Cross-tab storage changes detected and surfaced with reload/sync prompt.
- Optional `BroadcastChannel` sync strategy documented and implemented behind guard.
**Tests**:
- Unit tests simulating quota exceptions during persist.
- Integration tests for storage event prompt in two-tab scenario.
- Unit tests for conflict-resolution prompt throttling.
**Status**: Not Started

## Stage 3: Interrupted Work Recovery and Undo Framework
**Goal**: Normalize recovery from refresh interruptions and destructive actions.
**Success Criteria**:
- Rehydration converts stale `generating` artifacts to `failed` with interruption message.
- Shared undo manager handles delete/clear actions consistently with 5-second restore window.
- Soft-delete buffer purges only after undo timeout expires.
**Tests**:
- Unit tests for rehydrate migration of interrupted artifacts.
- Integration tests for undo manager restore/purge lifecycle.
- Regression tests across source/artifact/workspace/note destructive actions.
**Status**: Not Started

## Dependencies

- Undo manager should be consumed by Categories 1, 3, and 5.
