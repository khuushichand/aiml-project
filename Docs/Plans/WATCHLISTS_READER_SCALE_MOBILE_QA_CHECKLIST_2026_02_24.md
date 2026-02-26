# Watchlists Reader Scale + Mobile QA Checklist (2026-02-24)

## Scope

Validate Group 06 Stage 5 outcomes for Articles reader usability under mobile/narrow layouts and high-volume data.

## Dataset Profiles

- Profile A: 5 sources, low-volume daily review
- Profile B: 50 sources, medium-volume daily review
- Profile C: 200 sources, high-volume daily review

## Functional Scenarios

1. Reader loads with all three panes available (`left`, `list`, `reader`) at desktop width.
2. Reader remains operable at narrow/mobile width (source selection, item selection, include-in-next-briefing action).
3. Source list renders fully for Profile A without collapsed-window hint.
4. Source list uses collapsed render window for Profile C and expands on scroll.
5. Batch mark-all-filtered operation completes for high-volume item sets (>=1000 unread matches).
6. All-filtered lookup paginates in 200-item pages and reconciles full reviewed updates.

## Test Evidence

- Unit/helper coverage:
  - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/__tests__/items-utils.test.ts`
- Reader interaction + throughput coverage:
  - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.batch-controls.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.scale-responsive.test.tsx`
- Validation command:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/Watchlists/ItemsTab/__tests__/items-utils.test.ts src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.batch-controls.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.scale-responsive.test.tsx --maxWorkers=1 --no-file-parallelism`

## Pass Criteria

- All referenced test files pass.
- Profile A shows no source-window hint.
- Profile C shows source-window hint before scroll and hides it after full expansion.
- High-volume all-filtered flow confirms 1200-item execution with paginated lookup pages.
- No regressions in existing reader keyboard, batch, and preset workflows.

## Manual Spot Checks

- Confirm source-list hint text is readable and non-intrusive.
- Confirm scroll expansion does not jump selection state.
- Confirm mobile-narrow layout keeps review actions reachable without horizontal overflow.
- Confirm batch completion feedback remains clear for large-count operations.
