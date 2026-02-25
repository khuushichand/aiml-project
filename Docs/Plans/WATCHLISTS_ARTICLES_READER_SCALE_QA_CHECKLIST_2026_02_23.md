# Watchlists Articles Reader Scale QA Checklist (2026-02-23)

## Purpose

Validate Articles tab usability for daily triage across narrow viewport and high-volume scenarios.

## Scenario Matrix

| Scenario | Profile | Surface | Pass Criteria |
|---|---|---|---|
| AR-01 | 5-source profile | Articles tab (default triage) | Smart feeds, saved views, and reader actions are discoverable with no empty-state confusion. |
| AR-02 | 50-source profile | Articles tab (daily workload) | Batch controls show clear selected/page/all-filtered scope and completion messaging. |
| AR-03 | 200-source profile | Articles tab (high-density workload) | Sort modes and saved views remain responsive; row selection stays predictable. |
| AR-04 | 200+ filtered unread items | Articles tab batch review | All-filtered review operation completes with scoped confirmation and success/partial-failure feedback. |
| AR-05 | Mobile width (390px) | Articles tab layout | Left/list/reader panes and critical controls remain operable without keyboard trap regressions. |

## Manual Verification Steps

1. Confirm default triage behavior with 5 sources: smart-feed switching, search, and row selection.
2. Validate 50-source workflow: select-page, selected-scope review, and page-level review outcomes.
3. Validate 200-source workflow: switch sort modes and apply saved views repeatedly.
4. Run all-filtered review on a high unread set and verify partial-failure messaging if any updates fail.
5. Verify narrow viewport behavior (390px): shortcuts panel, batch controls, and reader action buttons.

## Automated Regression Gate

- Required test suites:
  - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/__tests__/items-utils.test.ts`
  - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.batch-controls.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx`
