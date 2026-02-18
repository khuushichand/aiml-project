# Implementation Plan: Chat Dictionaries - Import and Export

## Scope

Components: import/export controls in `apps/packages/ui/src/components/Option/Dictionaries/Manager.tsx`, import/export endpoints in `tldw_Server_API/app/api/v1/endpoints/chat_dictionaries.py`, schema validation paths, user-facing docs
Finding IDs: `5.1` through `5.6`

## Finding Coverage

- Multi-format import support and discoverability: `5.1`
- Safe import workflow with preview and confirmation: `5.2`
- Name conflict resolution and recovery UX: `5.3`
- Paste-based import ergonomics: `5.4`
- Preserve good export download behavior: `5.5`
- Markdown fidelity communication and safeguards: `5.6`

## Stage 1: Expand Import Inputs and Add Pre-Commit Preview
**Goal**: Prevent accidental imports and support JSON/Markdown parity.
**Success Criteria**:
- Import modal supports JSON and Markdown via selector or extension auto-detect.
- File and paste modes are both available in the same import flow.
- Parsing preview displays dictionary name, entry count, groups, and advanced-field usage.
- Import requires explicit confirmation after preview.
**Tests**:
- Component tests for format selection and paste/file mode toggling.
- Integration tests for JSON and Markdown preview parsing flows.
- E2E tests covering preview-confirm-import lifecycle.
**Status**: Not Started

## Stage 2: Conflict and Error Resolution
**Goal**: Turn import failures into actionable choices instead of dead ends.
**Success Criteria**:
- 409 conflict response triggers rename/replace/cancel resolution dialog.
- Rename path proposes deterministic next available name (e.g., `"(2)"` suffix).
- Replace path requires explicit destructive confirmation.
- Client-side schema pre-validation surfaces missing fields before API call.
**Tests**:
- Integration tests for 409 handling branches (rename/replace/cancel).
- Unit tests for deterministic rename suggestion helper.
- Component tests for client-side structural validation messaging.
**Status**: Not Started

## Stage 3: Export Fidelity Guarantees and Documentation
**Goal**: Preserve trust in exported data fidelity across formats.
**Success Criteria**:
- Existing direct download export behavior remains unchanged for JSON/Markdown.
- Markdown export warns when advanced fields may not round-trip fully.
- Docs clearly state JSON as full-fidelity format and list Markdown limitations.
- Export option copy reflects fidelity expectations before download.
**Tests**:
- Regression test for current filename and mime behavior.
- Integration tests for advanced-field warning conditions.
- Documentation check ensuring limitations are present and linked from UI.
**Status**: Not Started

## Dependencies

- Conflict-resolution behavior should align with optimistic concurrency handling in Category 8.
- Markdown round-trip behavior verification depends on server import/export serializer coverage.
