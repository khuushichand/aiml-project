# Implementation Plan: World Books - Bulk Operations

## Scope

Components: Entry bulk-action UX in entries drawer, selection semantics, bulk API usage, and inter-book batch workflows.
Finding IDs: `4.1` through `4.5`

## Finding Coverage

- Selection visibility and interaction model: `4.1`, `4.5`
- Missing operation parity with backend capabilities: `4.2`
- Cross-book reorganization and ecosystem import needs: `4.3`, `4.4`

## Stage 1: Improve Selection Feedback and Selection Scope
**Goal**: Make bulk state obvious and reduce accidental partial operations.
**Success Criteria**:
- Add a contextual bulk action bar that appears when `selected > 0`.
- Increase prominence of selected-count text and selected-state affordances.
- Add `Select all N entries` flow beyond current page selection behavior.
**Tests**:
- Component tests for action-bar visibility transitions and selected-count updates.
- Integration test for page-level select-all then full-dataset select-all escalation.
- Accessibility test for keyboard-triggered select-all flows.
**Status**: Not Started

## Stage 2: Add Bulk Set Priority
**Goal**: Expose existing backend `set_priority` support in UI.
**Success Criteria**:
- Add `Set Priority` bulk action with input control (slider or numeric field).
- Wire payload to `bulkOperate` with `operation: "set_priority"` and target IDs.
- Show post-operation summary toast including affected entry count.
**Tests**:
- Integration tests for successful priority updates and partial-failure handling.
- Unit tests for payload builder and input clamping (0-100).
- UI tests for confirmation and rollback/error messaging.
**Status**: Not Started

## Stage 3: Define and Implement Cross-Book Move Workflow
**Goal**: Support common reorganization workflows without delete-and-recreate churn.
**Success Criteria**:
- Define API contract for move/copy entries across world books.
- Add bulk `Move to world book` action with destination selector and conflict strategy.
- Preserve entry metadata (priority, flags) during move unless user overrides.
**Tests**:
- Backend integration tests for move semantics and conflict handling.
- UI integration tests for move confirmation, success summary, and failure reporting.
- Regression tests for source/destination counts after move.
**Status**: Not Started

## Stage 4: Add Interop Import Path for Community Formats
**Goal**: Allow high-volume onboarding from common lorebook ecosystems.
**Success Criteria**:
- Add batch import pathway for SillyTavern and Kobold formats with format detection.
- Normalize imported entries into internal schema and report conversion warnings.
- Reuse shared import converters with Category 6 plan to avoid duplicated logic.
**Tests**:
- Unit tests with fixture files for each supported format.
- Integration tests for conversion + bulk insert with warning summaries.
- Contract tests ensuring parser outputs valid internal entry payloads.
**Status**: Not Started

## Dependencies

- Stage 3 requires backend endpoint support if move is not currently available.
- Stage 4 should share converter module with Import/Export plan (`Category 6`) to keep behavior consistent.
