# Watchlists Monitor Density + Scale QA Checklist (2026-02-23)

## Purpose

Validate that monitor authoring and list surfaces remain readable and operable across baseline and high-density datasets.

## Scenario Matrix

| Scenario | Dataset Shape | Primary Surface | Pass Criteria |
|---|---|---|---|
| UC1-01 | 1 feed, 0 groups, 1 tag | Monitor form (Basic mode) | Review step shows `1 feed` scope and schedule guidance remains explicit. |
| UC1-02 | 10 feeds, mixed tags | Monitor form (Basic mode) | Review step keeps compact scope summary and no required-step confusion. |
| UC1-03 | 50 feeds, mixed tags | Monitor form (Basic mode) | Scope summary remains concise (`50 feeds`) and review handoff is clear. |
| UC1-04 | 200 sources | Sources tab | Table remains usable for bulk selection and group move actions. |
| UC1-05 | 200 monitors | Monitors tab | Compact summaries render for all rows; advanced columns are optional. |
| UC2-01 | 500 runs | Activity tab | Filters remain available and row rendering remains stable. |
| UC2-02 | 500 outputs | Reports tab | Filters remain available and row rendering remains stable. |

## Manual Validation Steps

1. Create baseline monitor in Basic mode with 1 feed, set schedule, advance to Review.
2. Repeat with 10 feeds; verify scope summary remains readable and review text is concise.
3. Repeat with 50 feeds; verify no extra hidden-step confusion and summary stays compact.
4. Load 200-source workspace and perform select + bulk move operation.
5. Load 200-monitor workspace and verify compact summaries render before enabling advanced columns.
6. Load 500-run workspace and verify advanced filters remain interactive.
7. Load 500-output workspace and verify advanced filters remain interactive.

## Regression Gate

- Required automated tests:
  - `apps/packages/ui/src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/JobsTab/__tests__/JobsTab.advanced-details.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.bulk-move.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.advanced-filters.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx`
