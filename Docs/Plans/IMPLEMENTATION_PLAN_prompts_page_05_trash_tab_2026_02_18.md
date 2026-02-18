# Implementation Plan: Prompts Page - Trash Tab

## Scope

Components: Trash tab table/actions in `apps/packages/ui/src/components/Option/Prompt/index.tsx`
Finding IDs: `5.1` through `5.4`

## Finding Coverage

- Discoverability in deleted items: `5.1`, `5.4`
- Retention visibility: `5.2`
- Recovery efficiency: `5.3`

## Stage 1: Trash Search and Content Visibility
**Goal**: Improve retrieval of deleted prompts without forced restoration.
**Success Criteria**:
- Trash tab adds search input filtering by prompt name.
- Trash rows include truncated content preview column or equivalent tooltip.
- Search and preview behavior remains performant with large trash sets.
**Tests**:
- Unit tests for trash filter predicate.
- Component tests for search input and preview rendering.
**Status**: Complete

## Stage 2: Auto-Purge Time Remaining Signals
**Goal**: Communicate urgency before permanent deletion windows expire.
**Success Criteria**:
- Trash rows display `days remaining` until auto-purge.
- Visual severity states applied for nearing expiry thresholds.
- Date math is timezone-safe and deterministic.
**Tests**:
- Unit tests for remaining-days calculation across date boundaries.
- Component tests for severity color/label thresholds.
**Status**: Complete

## Stage 3: Bulk Restore Workflow
**Goal**: Enable efficient recovery of multiple deleted prompts.
**Success Criteria**:
- Trash table adds row selection with `Restore selected` bulk action.
- Bulk restore returns summary (restored, failed) with retry option for failures.
- Individual restore/delete actions remain functional and consistent.
**Tests**:
- Integration tests for multi-select restore success and partial-failure scenarios.
- UI regression test ensuring row-level actions still function with selection enabled.
**Status**: Complete

## Dependencies

- Bulk-action behavior should align with partial-success patterns from Category 9.
