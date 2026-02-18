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
**Status**: Not Started

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
**Status**: Not Started

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
**Status**: Not Started

## Dependencies

- Global stats may need a dedicated backend endpoint to avoid expensive client-side aggregation.
- Token methodology note depends on exposing estimator identity from backend API where available.
