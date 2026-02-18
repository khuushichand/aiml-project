# Implementation Plan: World Books - List and Overview

## Scope

Components: `Manager.tsx` world book table, world-book query normalization, row action controls, table-level filters and sorting.
Finding IDs: `1.1` through `1.11`

## Finding Coverage

- Table intelligence and stale-state visibility: `1.1`, `1.2`, `1.3`, `1.7`
- List navigation and ranking controls: `1.5`, `1.6`
- Row affordance clarity and action consistency: `1.4`, `1.9`
- Productivity and onboarding gaps: `1.8`, `1.10`, `1.11`

## Stage 1: Surface Key Metadata in the Table
**Goal**: Make world-book health and freshness visible without opening modals.
**Success Criteria**:
- Add `Last Modified` column from `WorldBookResponse.last_modified` with relative and absolute tooltip timestamps.
- Add `Budget` column showing `token_budget` in compact form.
- Visually flag unattached books with an `Unattached` warning tag and optional row accent.
- Improve disabled-state distinction (`Disabled` tag color and/or dimmed row treatment).
**Tests**:
- Unit test for relative-time formatter and null-safe `last_modified` handling.
- Component test verifying `Last Modified`, `Budget`, and unattached indicators render from API payload.
- Snapshot/regression test for enabled vs disabled row visual states.
**Status**: Complete

## Stage 2: Add Search, Filters, and Sorting
**Goal**: Make large world-book collections navigable and quickly triageable.
**Success Criteria**:
- Add table search input filtering by world-book `name` and `description`.
- Add filter controls for `Enabled` state and `Has attachments` state.
- Add sorters for `Name`, `Entries`, and `Enabled` columns.
- Preserve filter/sort state during refetch and after mutation-triggered invalidations.
**Tests**:
- Component tests for text search (name and description) and combinational filters.
- Component tests for each sorter with ascending/descending behavior.
- Integration test validating state persistence through query invalidation.
**Status**: Complete

## Stage 3: Normalize Row Affordances and Actions
**Goal**: Make primary and secondary actions consistently discoverable and accessible.
**Success Criteria**:
- Replace ambiguous attachment popover trigger with explicit interactive affordance (count link and/or icon).
- Standardize row actions (either icon+tooltip with `aria-label`s or overflow menu for secondary actions).
- Ensure every icon-only action has explicit accessible naming and keyboard focusability.
**Tests**:
- Component test for attachment affordance rendering and click target behavior.
- Accessibility test for row actions (labels, focus order, keyboard activation).
- Visual regression test for action layout consistency across breakpoints.
**Status**: Complete

## Stage 4: Add Bulk Table Ops and Better Empty/Preview States
**Goal**: Improve startup guidance and high-volume maintenance workflows.
**Success Criteria**:
- Add row selection with bulk `Enable`, `Disable`, and `Delete` on world-book rows.
- Replace default empty table state with a custom onboarding empty state and CTA.
- Add lightweight entry preview via expandable rows (first 3-5 entries).
**Tests**:
- Integration test for multi-row bulk operations and post-mutation refetch behavior.
- Component test for custom empty state CTA navigation/open-create flow.
- Component test for expandable preview rendering and truncation behavior.
**Status**: Complete

## Dependencies

- Shared action-menu conventions should align with other workspace pages to avoid UI drift.
- Expandable preview requires a bounded payload strategy to avoid over-fetching in large books.

## Progress Notes (2026-02-18)

- Added list metadata helpers in `apps/packages/ui/src/components/Option/WorldBooks/worldBookListUtils.ts` for:
  - robust `last_modified` parsing (string/date/seconds)
  - relative + absolute timestamp rendering
  - null-safe fallback handling
- Updated world-book table in `apps/packages/ui/src/components/Option/WorldBooks/Manager.tsx`:
  - added `Last Modified` column with tooltip detail
  - added compact `Budget` column (`{token_budget} tok`)
  - replaced orphan dash with `Unattached` warning tag
  - improved disabled visibility via `volcano` status tag + dimmed row class
- Added search/filter/sorting controls to the main world-book list:
  - text search across name + description
  - enabled-state and attachment-state filters
  - controlled sort state for `Name`, `Entries`, and `Enabled` to persist through list updates
- Normalized table-row affordances and actions:
  - replaced ambiguous attachment tags with explicit attachment-count link button
  - standardized row actions as icon-only controls with consistent tooltips and `aria-label`s
- Added Stage 4 list workflow improvements:
  - world-book row selection with bulk `Enable`, `Disable`, and `Delete`
  - custom onboarding empty state with `Create your first world book` CTA
  - expandable row preview for first five entries via lazy-loaded preview query
- Added Stage 1 tests:
  - `apps/packages/ui/src/components/Option/WorldBooks/__tests__/worldBookListUtils.test.ts`
  - `apps/packages/ui/src/components/Option/WorldBooks/__tests__/WorldBooksManager.stage1.test.tsx`
- Added Stage 2 tests:
  - `apps/packages/ui/src/components/Option/WorldBooks/__tests__/WorldBooksManager.stage2.test.tsx`
- Added Stage 3 tests:
  - `apps/packages/ui/src/components/Option/WorldBooks/__tests__/WorldBooksManager.stage3.test.tsx`
- Expanded Stage 4 coverage in:
  - `apps/packages/ui/src/components/Option/WorldBooks/__tests__/WorldBooksManager.stage4.test.tsx`
