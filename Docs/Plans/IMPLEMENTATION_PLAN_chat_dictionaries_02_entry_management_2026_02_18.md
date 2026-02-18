# Implementation Plan: Chat Dictionaries - Entry Management

## Scope

Components: entry table and forms in `apps/packages/ui/src/components/Option/Dictionaries/Manager.tsx`, dictionary entry APIs in `tldw_Server_API/app/api/v1/endpoints/chat_dictionaries.py`, entry schemas in `tldw_Server_API/app/api/v1/schemas/chat_dictionary_schemas.py`
Finding IDs: `2.1` through `2.9`

## Finding Coverage

- Table density, filtering, and grouping ergonomics: `2.1`, `2.5`, `2.6`
- Editing workflows and advanced field exposure: `2.2`, `2.7`, `2.8`
- Batch operations and ordering semantics: `2.3`, `2.4`
- Interaction architecture (nested modal cleanup): `2.9`

## Stage 1: Entry Table Information Architecture
**Goal**: Make entry lists usable at medium and large scale.
**Success Criteria**:
- Entry table adds explicit columns for type, probability, and group.
- Search input filters entries by pattern/replacement/group text.
- Group dropdown filter uses server-supported `group` query and client fallback.
- Group field in forms supports autocomplete from existing dictionary groups.
**Tests**:
- Component tests for column rendering and responsive hide/show behavior.
- Integration tests for search + group filter composition.
- Unit tests for group autocomplete normalization (case-insensitive dedupe).
**Status**: Complete

## Stage 2: Faster Edit Flows with Advanced Options
**Goal**: Minimize modal churn for common edits while keeping advanced controls available.
**Success Criteria**:
- Pattern and replacement cells support inline edit commit/cancel states.
- Advanced edit modal remains available for probability, groups, and timed effects.
- Add/Edit forms expose timed effects (`sticky`, `cooldown`, `delay`) with units/tooltips.
- Regex validation workflow surfaces server-side safety feedback prior to save.
**Tests**:
- Component tests for inline edit keyboard and blur-save behavior.
- Integration tests for timed-effects create/update payload round-trip.
- API test confirming regex safety validation errors are surfaced in UI model.
**Status**: Complete

## Stage 3: Bulk Operations and Processing Order Controls
**Goal**: Enable efficient multi-entry maintenance for large dictionaries.
**Success Criteria**:
- Backend bulk endpoint exists for enable/disable/delete/set-group actions.
- Entry table supports row selection and contextual bulk action bar.
- Bulk operations return per-entry success/failure results for partial failures.
- Entry order behavior is explicitly documented and surfaced in UI.
- If ordering affects execution, drag handle or priority input is implemented.
**Tests**:
- Backend unit/integration tests for bulk endpoint validation and partial failures.
- Component tests for selection model and bulk action dispatch.
- Integration tests for reorder persistence and execution-order semantics.
**Status**: Complete
**Progress Notes (2026-02-18)**:
- Added backend `POST /dictionaries/entries/bulk` endpoint for `activate`, `deactivate`, `delete`, and `group` operations with partial-failure reporting.
- Added frontend row selection + contextual bulk action bar (enable/disable/delete/set-group) and preserved failed selections on partial failure.
- Added backend `PUT /dictionaries/{dictionary_id}/entries/reorder` endpoint and service-layer `sort_order` persistence for deterministic entry priority.
- Added UI priority controls (per-entry move up/down) that persist order through the reorder endpoint.
- Added Stage 3 component and endpoint tests for bulk action payloads, partial failures, and reorder dispatch.

## Stage 4: Replace Nested Modal Pattern
**Goal**: Remove modal-within-modal friction and improve focus flow.
**Success Criteria**:
- Entry manager migrates from nested modal pattern to drawer or sub-route.
- Edit entry surface no longer opens on top of a parent modal container.
- Focus management and return focus behavior remain deterministic.
**Tests**:
- Accessibility tests for focus trap and focus return behavior.
- E2E tests for entry management flow on desktop and mobile breakpoints.
**Status**: Not Started

## Dependencies

- Stage 3 bulk APIs must align with `BulkEntryOperation`/`BulkOperationResponse` schema contracts.
- Stage 4 layout decisions should align with responsive constraints in Category 9.
