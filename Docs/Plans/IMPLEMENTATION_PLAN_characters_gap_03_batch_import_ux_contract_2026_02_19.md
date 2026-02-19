# Implementation Plan: Characters Gap 03 - Batch Import UX Contract (2026-02-19)

## Issue Summary

Batch import implementation does not fully match planned UX around drag-and-drop and granular per-file runtime status.

## Stage 1: Finalize UX and State Model
**Goal**: Define complete state machine for batch import, including drag-drop and per-file lifecycle.
**Success Criteria**:
- File states are defined (`queued`, `processing`, `success`, `failure`).
- Drag-drop behavior is specified for single and multi-file input.
- Aggregate summary contract remains compatible with existing UI.
**Tests**:
- Unit tests for import reducer/state transitions.
- UI tests for drag enter/leave/drop behavior.
**Status**: Complete
**Update (2026-02-19)**:
- Added canonical import lifecycle/drag-drop state model in `apps/packages/ui/src/components/Option/Characters/import-state-model.ts`.
- Defined reducer/actions for queue lifecycle transitions and a batch summary contract compatible with existing success/failure notification semantics.
- Added upload callback gating helper to make single-vs-batch event handling explicit and deterministic.
- Wired `Manager.tsx` upload dedupe logic to `shouldHandleImportUploadEvent` from the shared state model.
- Added unit coverage in `apps/packages/ui/src/components/Option/Characters/__tests__/import-state-model.test.ts`.
- Verified import-preview/import-confirm behavior remains stable via targeted `Manager.first-use` import tests.

## Stage 2: Implement Drag-Drop and Status Instrumentation
**Goal**: Add drag-drop ingestion and per-file status rendering in import UI.
**Success Criteria**:
- Users can import files by drop zone and picker.
- Per-file status updates render in real-time during processing.
- Final summary includes aggregate counts and per-file errors.
**Tests**:
- Component tests for drag-drop multi-file ingestion.
- Integration test for mixed-validity batches and transitions.
**Status**: Complete
**Update (2026-02-19)**:
- Added a visible drop zone around import controls in `Manager.tsx` with drag-enter/leave/over/drop handlers and drop ingestion wired to the existing preview flow.
- Kept picker upload path in place and aligned both ingestion paths through shared preview/open logic.
- Added per-file runtime status rendering in import preview (`queued`/`processing`/`success`/`failure`) backed by the shared import queue reducer.
- Added import progress summary block showing queued/processing/success/failure counts during confirm processing.
- Updated confirm flow to process files while preview remains open so runtime statuses render in real time.
- Added manager tests for drop-zone ingestion and runtime status transitions in mixed-success/failure batches.

## Stage 3: Harden with E2E and Failure Recovery
**Goal**: Validate full batch flow under retries, partial failures, and cancellation.
**Success Criteria**:
- E2E flow validates preview, confirm, processing, and summary.
- Recoverable file failures do not block entire batch.
- Retry path works for failed files without duplicate imports.
**Tests**:
- E2E test for mixed outcomes and summary correctness.
- Integration test for retry-only-failed behavior.
**Status**: Complete
**Update (2026-02-19)**:
- Added retry-only-failed UI path in import preview (`Retry failed`) that reprocesses only items currently marked `failure`.
- Added manager integration coverage verifying retry avoids re-importing already successful files.
- Existing cancel-before-import behavior remains covered.
- Added extension E2E coverage in `apps/extension/tests/e2e/characters-create-edit-import-export.spec.ts` for preview/confirm/processing/summary with mixed import outcomes and retry-failed behavior.
