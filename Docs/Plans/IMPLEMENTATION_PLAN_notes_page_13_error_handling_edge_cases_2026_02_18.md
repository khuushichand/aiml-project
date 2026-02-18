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
**Status**: Not Started

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
**Status**: Not Started

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
**Status**: Not Started

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
**Status**: Not Started

## Dependencies

- Trash/restore semantics should remain consistent with Plan 10.
- Link dependency signals should reuse graph relationships from Plan 06.
