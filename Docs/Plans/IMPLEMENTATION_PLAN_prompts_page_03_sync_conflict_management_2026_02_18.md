# Implementation Plan: Prompts Page - Sync and Conflict Management

## Scope

Components: `apps/packages/ui/src/services/prompt-sync.ts`, `SyncStatusBadge.tsx`, `PromptActionsMenu.tsx`, `ProjectSelector.tsx`, prompt toolbar/actions in `index.tsx`
Finding IDs: `3.1` through `3.6`

## Finding Coverage

- Conflict resolution UX gap: `3.1`
- Sync failure visibility and status context: `3.2`, `3.6`
- Batch sync operations and project ergonomics: `3.3`, `3.5`
- Conflict detection quality: `3.4`

## Stage 1: Conflict Resolution End-to-End UI
**Goal**: Provide a complete, non-lossy conflict workflow.
**Success Criteria**:
- Conflict badge and actions menu open a `ConflictResolutionModal`.
- Modal shows side-by-side local/server prompt content and metadata.
- Resolution actions map directly to `keep_local`, `keep_server`, `keep_both`.
- Successful resolution updates row status and local/server linkage immediately.
**Tests**:
- Integration tests for modal launch from badge and menu entry points.
- Unit tests for resolution-action mapping and state transitions.
- Integration test for each resolution path with mocked sync service responses.
**Status**: Not Started

## Stage 2: Sync Failure Transparency and Offline Context Retention
**Goal**: Ensure users understand sync state and failures without opening dev tools.
**Success Criteria**:
- Auto-sync failure shows warning toast with actionable message.
- Prompts area includes pending-sync count indicator when failures/pending exist.
- Sync status column remains visible offline with muted presentation and tooltip.
- Empty `ProjectSelector` state supports inline project creation.
**Tests**:
- Component tests for failure toast and pending-count badge behavior.
- Component tests for offline sync-column rendering and tooltip content.
- Integration test for inline project creation from empty selector state.
**Status**: Not Started

## Stage 3: Batch Sync Operations
**Goal**: Reduce repetitive per-prompt sync actions for large libraries.
**Success Criteria**:
- Toolbar exposes `Sync all` when actionable items exist.
- Batch process supports push/pull candidates discovered via sync-status scan.
- Progress UI reports completed/total with partial-failure summaries.
- Batch operation remains cancellable or safely retryable.
**Tests**:
- Unit tests for actionable-item selection from status list.
- Integration tests for batch sync progress and partial failure handling.
- UI regression test for toolbar visibility rules.
**Status**: Not Started

## Stage 4: Conflict Detection Hardening
**Goal**: Reduce false-positive conflicts while preserving true conflict detection.
**Success Criteria**:
- Conflict check combines timestamp and deterministic content-hash comparison.
- Metadata-only server updates no longer produce conflict status.
- Existing timestamp fields remain backward compatible for migrated records.
**Tests**:
- Unit tests for hash generation and conflict predicate matrix.
- Integration tests for metadata-only and content-change scenarios.
**Status**: Not Started

## Dependencies

- Batch-sync and bulk flows should align with Custom tab bulk operations plan.
- Project creation path should reuse Studio project service contracts.
