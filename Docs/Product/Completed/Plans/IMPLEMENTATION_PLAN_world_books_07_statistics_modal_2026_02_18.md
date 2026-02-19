# Implementation Plan: World Books - Statistics Modal

## Scope

Components: World-book statistics modal, stats query responses, drill-down interactions, and budget visualization.
Finding IDs: `7.1` through `7.4`

## Finding Coverage

- Actionability from statistics: `7.1`
- Global visibility gaps: `7.2`
- Token estimation transparency: `7.3`
- Budget utilization and over-budget risk signaling: `7.4`

## Stage 1: Make Statistics Actionable
**Goal**: Convert static metrics into navigation shortcuts for remediation.
**Success Criteria**:
- Add click actions on key metric rows (disabled entries, regex entries, etc.) to open filtered entry drawer.
- Preserve selected filters when deep-linking from stats to entries.
- Provide clear affordance that statistic rows are interactive.
**Tests**:
- Integration tests for metric click -> drawer open -> expected filters applied.
- Component tests for interactive row states and keyboard activation.
- Regression tests for non-interactive rows remaining static.
**Status**: Complete

## Stage 2: Add Budget Utilization with Method Transparency
**Goal**: Make token-cost risk understandable and operationally useful.
**Success Criteria**:
- Display token budget, estimated tokens, and utilization percentage in modal.
- Add utilization progress bar with threshold colors (green/amber/red).
- Add note clarifying estimation methodology/tokenizer source.
**Tests**:
- Unit tests for utilization percentage and threshold-color mapping.
- Component tests for over-budget warning behavior.
- Contract tests ensuring estimator note reflects backend method metadata when available.
**Status**: Complete

## Stage 3: Introduce Global Statistics View
**Goal**: Give authors and admins a cross-book lens on coverage and conflicts.
**Success Criteria**:
- Add global statistics entry point from world-books page.
- Show aggregate totals (books, entries, keywords, estimated tokens, aggregate budgets).
- Include cross-book keyword conflict counts and drill-down links.
**Tests**:
- Integration tests for global stats aggregation correctness.
- Component tests for conflict listing and drill-down navigation.
- Performance test for aggregate computation on large datasets.
**Status**: Complete

## Dependencies

- Global stats may need a dedicated backend endpoint to avoid expensive client-side aggregation.
- Token methodology note depends on exposing estimator identity from backend API where available.

## Progress Notes (2026-02-18)

- Implemented Stage 1 actionable statistics behavior in `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorldBooks/Manager.tsx`:
  - added interactive drill-down actions in statistics modal for:
    - enabled entries
    - disabled entries
    - regex entries
  - drill-down now closes the modal and opens the entries drawer with preset filters.
  - added visible affordance copy in the modal ("click linked metrics...") for discoverability.
  - preserved deep-link intent by passing explicit filter presets into `EntryManager`.
- Extended entry filtering in `EntryManager`:
  - added `entryFilterPreset` support from parent.
  - added match-type filtering (`all`, `regex`, `plain`) in both state and UI controls.
  - ensured preset filters are applied when opening the drawer from statistics.
- Added Stage 1 tests:
  - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorldBooks/__tests__/WorldBooksManager.statisticsStage1.test.tsx`
    - verifies disabled metric click opens drawer with disabled filter and filtered rows.
    - verifies keyboard activation on regex metric drill-down.
    - verifies zero-value drill-down rows stay non-interactive.
- Validation run:
  - `bunx vitest run src/components/Option/WorldBooks/__tests__/WorldBooksManager.statisticsStage1.test.tsx src/components/Option/WorldBooks/__tests__/WorldBooksManager.importExportStage4.test.tsx src/components/Option/WorldBooks/__tests__/WorldBooksManager.importExportStage3.test.tsx`
  - result: **3 passed / 3 files**, **8 passed / 8 tests**.
- Implemented Stage 2 budget/utilization transparency:
  - added stats utilities in `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorldBooks/worldBookStatsUtils.ts`:
    - `getBudgetUtilizationPercent`
    - `getBudgetUtilizationBand`
    - `getBudgetUtilizationColor`
    - `getTokenEstimatorNote`
  - updated statistics modal in `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorldBooks/Manager.tsx` to show:
    - token budget value
    - utilization fraction + percentage
    - color-coded utilization progress bar
    - over-budget warning copy
    - estimator methodology note (backend metadata when present, fallback approximation otherwise)
- Added Stage 2 tests:
  - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorldBooks/__tests__/worldBookStatsUtils.test.ts`
    - unit coverage for percentage math, threshold bands, color mapping, and estimator-note metadata handling.
  - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorldBooks/__tests__/WorldBooksManager.statisticsStage2.test.tsx`
    - component coverage for over-budget warning + utilization display.
    - contract-style coverage for estimator method metadata rendering.
- Validation run:
  - `bunx vitest run src/components/Option/WorldBooks/__tests__/worldBookStatsUtils.test.ts src/components/Option/WorldBooks/__tests__/WorldBooksManager.statisticsStage1.test.tsx src/components/Option/WorldBooks/__tests__/WorldBooksManager.statisticsStage2.test.tsx src/components/Option/WorldBooks/__tests__/WorldBooksManager.importExportStage4.test.tsx`
  - result: **4 passed / 4 files**, **13 passed / 13 tests**.
- Implemented Stage 3 global statistics view:
  - added global stats aggregator utility in `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorldBooks/worldBookGlobalStatsUtils.ts`:
    - computes total books/entries/keywords/tokens/budget
    - computes shared-keyword counts and cross-book conflict rows
    - includes per-conflict affected book mapping for drill-down actions
  - added "Global Statistics" entry point and modal in `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorldBooks/Manager.tsx`:
    - header action button to open modal
    - aggregate metrics display
    - global budget utilization progress row
    - cross-book conflict list with per-book drill-down links
  - added keyword-aware deep-link support into entries drawer:
    - expanded `EntryFilterPreset` with `searchText`
    - global conflict click opens entries drawer pre-filtered to selected keyword
- Added Stage 3 tests:
  - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorldBooks/__tests__/worldBookGlobalStatsUtils.test.ts`
    - aggregation correctness for totals/conflicts
    - performance sanity coverage on large synthetic dataset
  - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorldBooks/__tests__/WorldBooksManager.statisticsStage3.test.tsx`
    - validates global stats modal rendering
    - validates conflict drill-down opens entries drawer with keyword search preset
- Validation run:
  - `bunx vitest run src/components/Option/WorldBooks/__tests__/worldBookGlobalStatsUtils.test.ts src/components/Option/WorldBooks/__tests__/WorldBooksManager.statisticsStage1.test.tsx src/components/Option/WorldBooks/__tests__/WorldBooksManager.statisticsStage2.test.tsx src/components/Option/WorldBooks/__tests__/WorldBooksManager.statisticsStage3.test.tsx`
  - result: **4 passed / 4 files**, **9 passed / 9 tests**.
