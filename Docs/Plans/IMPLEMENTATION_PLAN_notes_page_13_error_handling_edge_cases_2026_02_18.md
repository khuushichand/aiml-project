# Implementation Plan: Notes Page - Error Handling & Edge Cases

## Scope

Components/pages: destructive operations, warning/recovery flows, partial success messaging, export and keyword failure handling.
Finding IDs: `13.1` through `13.7`

## Finding Coverage

- Preserve effective current error patterns: `13.1`, `13.2`, `13.3`
- Add deletion undo and dependency-aware warnings: `13.4`, `13.5`
- Strengthen export warning visibility and preflight: `13.6`
- Surface keyword partial-attachment failures: `13.7`

## Stage 1: Delete Undo Path
**Goal**: Provide immediate recovery for accidental deletions.
**Success Criteria**:
- Show actionable `Note deleted - Undo` toast with timeout.
- Wire undo action to restore endpoint and refresh list state.
- Handle restore failures with explicit fallback instructions.
**Tests**:
- Integration tests for delete -> undo success flow.
- Timeout behavior tests for undo window expiration.
- Error tests for restore failure messaging.
**Status**: Complete

## Stage 2: Link-Aware Delete Safeguards
**Goal**: Warn users before breaking note-link relationships.
**Success Criteria**:
- Detect inbound link count prior to delete confirmation.
- Show warning message when referenced by other notes.
- Preserve ability to proceed with explicit confirmation.
**Tests**:
- Integration tests for warning visibility at zero vs non-zero inbound links.
- Confirmation flow tests for proceed/cancel outcomes.
- Regression tests for delete API behavior when links exist.
**Status**: Complete

## Stage 3: Partial Success and Attachment Failure Messaging
**Goal**: Make mixed-outcome saves transparent.
**Success Criteria**:
- Surface warning toast when note save succeeds but keyword attachment partially fails.
- Include count/details summary without exposing sensitive internals.
- Keep note content persisted even if some keyword operations fail.
**Tests**:
- API contract tests for partial-success response envelope.
- Integration tests for warning toast copy and retry guidance.
- Regression tests for state consistency after partial failures.
**Status**: Complete

## Stage 4: Export Risk Preflight and Recovery
**Goal**: Reduce missed warnings during high-volume exports.
**Success Criteria**:
- Show pre-export confirmation dialog when export size exceeds threshold.
- Provide estimated scope before user confirms start.
- Preserve existing toast as secondary signal during runtime.
**Tests**:
- Integration tests for threshold-triggered preflight dialog.
- UX tests for confirm/cancel branching behavior.
- Regression tests for existing export limit enforcement.
**Status**: Complete

## Dependencies

- Trash/restore semantics should remain consistent with Plan 10.
- Link dependency signals should reuse graph relationships from Plan 06.

## Progress Notes (2026-02-18)

### Stage 1 completion

- Added delete-undo toast flow in:
  - `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
    - post-delete toast now includes actionable `Undo` control
    - undo path resolves deleted-note version from trash endpoint
    - successful undo restores note and rehydrates editor/list state
    - explicit fallback messaging when undo is unavailable/fails
- Added Stage 1 tests:
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage32.delete-undo.test.tsx`
    - validates delete->undo restore success flow
    - validates fallback warning when undo version cannot be resolved

### Stage 2 completion

- Added inbound-link-aware delete confirmation warnings in:
  - `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
    - computes inbound reference count from note-neighbors graph edges
    - augments delete confirmation copy when references exist
    - preserves baseline confirmation copy when no references are present
- Added Stage 2 tests:
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage33.link-aware-delete-warning.test.tsx`
    - validates warning visibility for referenced notes
    - validates baseline confirmation path for unreferenced notes

### Stage 3 completion

- Added partial keyword-attachment failure response metadata in:
  - `/tldw_Server_API/app/api/v1/schemas/notes_schemas.py`
    - new `NoteKeywordSyncStatus` schema
    - `NoteResponse.keyword_sync` optional field
  - `/tldw_Server_API/app/api/v1/endpoints/notes.py`
    - `_sync_note_keywords()` now returns failure summary
    - create/update/patch responses attach `keyword_sync` when failures occur
- Surfaced partial-save warning messaging in:
  - `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
    - parses `keyword_sync` response metadata
    - shows warning toast while preserving successful note save flow
- Added Stage 3 tests:
  - `/tldw_Server_API/tests/Notes/test_notes_api_integration.py`
    - `test_create_note_surfaces_keyword_partial_failures`
    - `test_update_note_surfaces_keyword_partial_failures`
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage34.keyword-partial-save-warning.test.tsx`
    - validates warning toasts for create/update partial keyword failures

### Stage 4 completion

- Added export preflight confirmation for large exports in:
  - `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
    - preflight threshold set to 100,000 notes (aligned with export page cap)
    - requires explicit confirmation before starting high-volume export
    - keeps existing runtime partial-data warnings as secondary signals
- Added Stage 4 tests:
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage35.export-preflight.test.tsx`
    - validates cancel branch aborts export
    - validates confirm branch proceeds with export
