# Implementation Plan: Media Pages - Trash Management (/media-trash)

## Scope

Pages/components: `MediaTrashPage.tsx`, trash list items, restore/delete flows, delete feedback from `/media`
Finding IDs: `8.1` through `8.7`

## Finding Coverage

- Preserve strong current trash behaviors: `8.1`, `8.3`, `8.4`
- Improve trash item context and policy visibility: `8.2`, `8.6`
- Add recovery and discovery improvements: `8.5`, `8.7`

## Stage 1: Immediate Undo for Soft-Delete
**Goal**: Reduce accidental-delete anxiety and unnecessary navigation to trash.
**Success Criteria**:
- Soft-delete from `/media` shows toast with "Undo" action.
- Undo calls restore API and refreshes impacted lists.
- Undo timeout and race conditions are handled predictably.
**Tests**:
- Integration tests for delete -> undo restore flow.
- Unit tests for toast lifecycle and callback behavior.
- Regression tests for delete behavior when toast expires.
**Status**: Not Started

## Stage 2: Trash Item Context Enrichment
**Goal**: Improve decision quality when restoring or permanently deleting items.
**Success Criteria**:
- Trash rows display deletion timestamp where available.
- Retention policy text appears when policy config exists.
- Missing policy state is explicit (no implied auto-purge).
**Tests**:
- Component tests for deletion date rendering and fallback copy.
- Integration tests for retention policy display toggles.
- Snapshot tests for trash row layout with added metadata.
**Status**: Not Started

## Stage 3: Trash Search and Bulk-Flow Regression Safety
**Goal**: Improve trash navigation while preserving robust bulk operations.
**Success Criteria**:
- Search/filter input added for trash list.
- Search integrates with pagination and selected-item state safely.
- Existing batched bulk operations, cancel support, and partial-success messaging remain intact.
**Tests**:
- Integration tests for trash search query + pagination behavior.
- Regression tests for bulk restore/delete with mixed outcomes.
- Abort-flow tests for canceling batched operations.
**Status**: Not Started

## Dependencies

- Undo implementation should be shared with Category 13 (`13.5`) to avoid duplicate logic.
