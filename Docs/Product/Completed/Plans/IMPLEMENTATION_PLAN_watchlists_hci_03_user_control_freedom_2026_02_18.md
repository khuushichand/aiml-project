# Implementation Plan: Watchlists H3 - User Control and Freedom

## Scope

Route/components: `SourcesTab`, `SourcesBulkImport`, `RunsTab`, `TemplatesTab`, shared destructive-action flows  
Finding IDs: `H3.1` through `H3.5`

## Finding Coverage

- No undo path for destructive actions: `H3.1`, `H3.2`
- No pre-commit preview for high-impact imports: `H3.3`
- Missing cancellation controls for in-flight work: `H3.4`
- Template deletion safety gaps: `H3.5`

## Stage 1: Undo and Soft-Delete Foundation
**Goal**: Make destructive actions reversible for a short window.
**Success Criteria**:
- Source/job deletion actions show toast with timed undo.
- Bulk delete/disable actions support undo where technically feasible.
- Backend/API contract clearly defines reversible window and finalization behavior.
**Tests**:
- Component tests for delete -> undo -> restore flow.
- Integration tests for timeout expiration and irreversible finalization.
- Regression tests for permission enforcement in undo paths.
**Status**: Complete

## Stage 2: Preflight and Safety Prompts
**Goal**: Prevent irreversible mistakes before action submission.
**Success Criteria**:
- OPML import offers dry-run preview (new/duplicate/invalid counts) before commit.
- Template delete warns when template is referenced by active jobs.
- Bulk operations summarize impact before execution.
**Tests**:
- Integration tests for OPML dry-run result states and commit path.
- Component tests for dependency warning dialogs.
- E2E test for safe bulk action confirmation UX.
**Status**: Complete

## Stage 3: Active Run Cancellation
**Goal**: Let users stop mistaken or runaway runs from the UI.
**Success Criteria**:
- Runs table and run detail drawer expose cancel action for cancellable statuses.
- Cancel action shows progress state (`cancelling`, `cancelled`, `failed-to-cancel`).
- Cancellation result is reflected in logs and summary counts.
**Tests**:
- Integration tests for cancel action API success/failure states.
- Component tests for action gating by run status.
- E2E test for start run -> cancel -> confirmed terminal state.
**Status**: Complete

## Dependencies

- Undo model should align with backend retention and soft-delete policies.
- Cancel action depends on server-side run interruption semantics and authorization checks.

## Progress Notes

- 2026-02-18: Implemented source delete and bulk-delete undo notifications in `SourcesTab` using a 10-second restore window and recreate-on-undo flow.
- 2026-02-18: Implemented monitor delete undo notification in `JobsTab` using the same 10-second restore window.
- 2026-02-18: Added bulk enable/disable undo in `SourcesTab` to restore prior active states when needed.
- 2026-02-18: Added OPML import preflight preview (dry-run style) with duplicate/invalid counts before commit in `SourcesBulkImport`.
- 2026-02-18: Added template delete safety check to warn when active monitors reference the template before confirming delete.
- 2026-02-18: Added bulk action preflight confirmations (enable/disable/delete) with impact summaries in `SourcesTab`.
- 2026-02-18: Added targeted unit tests for OPML preflight parsing, template usage detection, and bulk-action summaries.
- 2026-02-18: Added `POST /api/v1/watchlists/runs/{run_id}/cancel` endpoint and backend tests for running/terminal cancellation behavior.
- 2026-02-18: Added run-cancel controls to `RunsTab` and `RunDetailDrawer` with in-flight progress (`Cancelling...`), success, and retry-on-failure states.
- 2026-02-18: Added UI tests for cancellation gating/success (`RunsTab.cancel-run.test.tsx`) and extension E2E coverage for activity cancel flow (`watchlists.spec.ts`).
- 2026-02-18: Added component undo-path regression for monitor delete -> undo restore in `JobsTab.undo-delete.test.tsx`.
- 2026-02-18: Added OPML preflight + commit integration coverage in `SourcesBulkImport.preflight-commit.test.tsx` (ready/duplicate parsing and commit gating).
- 2026-02-18: Added template dependency warning component coverage in `TemplatesTab.delete-safety.test.tsx` for in-use and not-in-use deletion prompts.
- 2026-02-18: Added extension E2E case for bulk disable impact-confirmation summary (`watchlists.spec.ts`, `feeds bulk disable shows impact summary before commit`); runtime execution is currently blocked in this environment by Chromium persistent-context startup timeouts.
- 2026-02-18: Added undo-window finalization refresh hooks (`onDismiss`) for source and monitor deletion/toggle flows so state re-syncs when undo expires without restore.
- 2026-02-18: Added undo finalization and helper regressions:
  - `JobsTab.undo-delete.test.tsx` now verifies 10-second undo duration and expiration refresh behavior.
  - `useUndoNotification.test.tsx` verifies dismiss/undo/error semantics.
  - `source-undo.test.ts` includes permission-denied restore failure accounting (`403 forbidden` path).
