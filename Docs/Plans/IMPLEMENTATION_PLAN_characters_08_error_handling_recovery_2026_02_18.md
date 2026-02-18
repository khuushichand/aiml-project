# Implementation Plan: Characters - Error Handling and Recovery

## Scope

Components: `apps/packages/ui/src/components/Option/Characters/Manager.tsx`, `apps/packages/ui/src/services/tldw/TldwApiClient.ts`, character persistence endpoints in `tldw_Server_API/app/api/v1/endpoints/characters_endpoint.py`
Finding IDs: `C-24` through `C-26`

## Finding Coverage

- Name length mismatch between UI and backend constraints: `C-24`
- Recovery model ends after undo toast with no trash surface: `C-25`
- Bulk delete messaging conflicts with soft-delete behavior: `C-26`

## Stage 1: Align Name-Length Contract Across UI and API
**Goal**: Eliminate silent truncation/confusion for long names.
**Success Criteria**:
- UI enforces explicit max length consistent with chosen product constraint.
- Helper/counter messaging communicates current limit at entry time.
- Display truncation strategy matches stored value expectations.
**Tests**:
- Component tests for `maxLength` enforcement and counter behavior.
- API integration tests verifying validation errors/messages for oversized names.
- Regression test for list rendering with edge-length names.
**Status**: Not Started

## Stage 2: Unify Delete Semantics and User Messaging
**Goal**: Ensure single and bulk delete flows communicate the same truth.
**Success Criteria**:
- Bulk delete flow uses same soft-delete + undo semantics or explicitly different behavior with accurate copy.
- Confirmation and toast messages are consistent across single and bulk paths.
- Deletion notifications include recoverability window details.
**Tests**:
- Component tests for bulk delete confirm copy and action path.
- Integration tests for undo behavior in bulk and single delete.
- i18n tests for delete/recovery copy parity.
**Status**: Not Started

## Stage 3: Implement Recently Deleted Recovery Surface
**Goal**: Provide recovery after undo toast timeout expires.
**Success Criteria**:
- Characters workspace includes "Recently deleted" tab/filter for soft-deleted records.
- Restore action is available for eligible records (e.g., 30-day window).
- Deleted-state listing clearly distinguishes from active records.
**Tests**:
- Backend tests for soft-deleted query + restore behavior.
- Component tests for deleted list rendering and restore action.
- Integration tests for delete -> toast timeout -> restore from trash flow.
**Status**: Not Started

## Stage 4: Operational Hardening and Observability
**Goal**: Detect and debug recovery-flow failures early.
**Success Criteria**:
- Restore failures produce actionable error messaging.
- Optional telemetry captures delete/undo/restore events for regression monitoring.
- Recovery policy is documented in user and developer docs.
**Tests**:
- Integration tests for restore conflict/error paths.
- QA checklist for policy messaging and edge-case behavior.
**Status**: Not Started

## Dependencies

- Stage 3 depends on existing soft-delete backend fields being queryable via list endpoint extensions.
- Stage 2 should coordinate with global destructive-action messaging standards in the UI package.
