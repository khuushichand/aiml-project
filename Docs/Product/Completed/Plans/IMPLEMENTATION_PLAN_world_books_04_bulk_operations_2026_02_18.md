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
**Status**: Complete

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
**Status**: Complete

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
**Status**: Complete

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
**Status**: Complete

## Dependencies

- Stage 3 requires backend endpoint support if move is not currently available.
- Stage 4 should share converter module with Import/Export plan (`Category 6`) to keep behavior consistent.

## Progress Notes (2026-02-18)

- Implemented Stage 1 in `apps/packages/ui/src/components/Option/WorldBooks/Manager.tsx`:
  - replaced always-visible bulk controls with a contextual action bar shown only when entries are selected.
  - promoted selected count to a more prominent treatment.
  - added escalation controls: `Select all N entries` and `Clear selection`.
  - added keyboard-accessible select-all action (`button` with explicit aria-label).
- Added Stage 1 tests:
  - `apps/packages/ui/src/components/Option/WorldBooks/__tests__/WorldBooksManager.bulkOperationsStage1.test.tsx`
  - validates visibility transitions, select-all escalation, and keyboard-triggered activation.
- Implemented Stage 2 in `apps/packages/ui/src/components/Option/WorldBooks/Manager.tsx`:
  - added `Set Priority` bulk action with popover + numeric input.
  - wired payload to backend operation `set_priority` via shared payload builder.
  - added success and partial-failure toast summaries using backend `affected_count` and `failed_ids`.
  - hardened bulk action handlers against thrown mutation errors (relying on mutation-level error notifications).
- Added Stage 2 utilities and tests:
  - `apps/packages/ui/src/components/Option/WorldBooks/worldBookBulkActionUtils.ts`
  - `apps/packages/ui/src/components/Option/WorldBooks/__tests__/worldBookBulkActionUtils.test.ts`
  - `apps/packages/ui/src/components/Option/WorldBooks/__tests__/WorldBooksManager.bulkOperationsStage2.test.tsx`
  - validates payload normalization/clamping, successful set-priority, partial-failure messaging, and request-failure messaging.
- Implemented Stage 3 in `apps/packages/ui/src/components/Option/WorldBooks/Manager.tsx`:
  - added bulk `Move To` workflow with destination world-book selector and conflict strategy (`skip_existing` / `duplicate`).
  - preserves entry metadata when copying to destination, then bulk-deletes moved source entries.
  - added warnings/summaries for moved, skipped, and failed entry outcomes.
- Added Stage 3 API contract/design note:
  - `Docs/Design/WORLD_BOOK_ENTRY_MOVE_API_CONTRACT_2026_02_18.md`
  - documents proposed backend move endpoint while current UI uses copy+delete fallback.
- Added Stage 3 tests:
  - `apps/packages/ui/src/components/Option/WorldBooks/__tests__/WorldBooksManager.bulkOperationsStage3.test.tsx`
  - validates skip-existing behavior, metadata preservation, and source deletion semantics.
- Implemented Stage 4 in `apps/packages/ui/src/components/Option/WorldBooks/worldBookInteropUtils.ts` and `apps/packages/ui/src/components/Option/WorldBooks/Manager.tsx`:
  - added import-format detection for `tldw`, `SillyTavern`, and `Kobold`.
  - added conversion pipeline to normalize external formats into internal world-book payloads.
  - surfaced detected format + conversion warnings in import preview.
- Added Stage 4 tests:
  - `apps/packages/ui/src/components/Option/WorldBooks/__tests__/worldBookInteropUtils.test.ts`
  - `apps/packages/ui/src/components/Option/WorldBooks/__tests__/WorldBooksManager.bulkOperationsStage4.test.tsx`
  - validates format detection/conversion and import integration flow.
- Validation run:
  - `bunx vitest run src/components/Option/WorldBooks/__tests__` (from `apps/packages/ui`)
  - result: **20 passed / 20 files**, **56 passed / 56 tests**.
