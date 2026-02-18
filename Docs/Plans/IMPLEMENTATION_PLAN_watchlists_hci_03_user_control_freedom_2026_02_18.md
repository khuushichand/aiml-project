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
**Status**: Not Started

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
**Status**: Not Started

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
**Status**: Not Started

## Dependencies

- Undo model should align with backend retention and soft-delete policies.
- Cancel action depends on server-side run interruption semantics and authorization checks.
