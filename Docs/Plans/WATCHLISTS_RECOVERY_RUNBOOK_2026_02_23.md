# Watchlists Recovery Runbook (2026-02-23)

## Purpose

Provide a repeatable response path for the most common Watchlists failure classes so QA, support, and engineering can restore user workflows quickly.

## Failure Classes and UI Recovery Actions

| Failure Class | Detection Surface | Primary User Action | Escalation Trigger |
|---|---|---|---|
| Feed fetch/test failure | Feeds + Overview attention | Retry feed test, validate URL/type, save after successful test | Same feed fails 3 consecutive retries |
| Monitor validation/save failure | Monitors form inline errors | Correct blocker (schedule/recipient/filter), re-submit | Blocking error persists after valid payload |
| Run failure/stall | Activity + run notifications | Open run detail, inspect error/log, retry or cancel/re-run | >20% failed or stalled runs in 24h |
| Output delivery failure | Reports delivery status + filters | Filter failed deliveries, open linked run/monitor, regenerate output | Delivery failures on >=10 outputs/day |
| Preview/render failure | Reports preview and template preview warnings | Regenerate with validated template/version or fallback template | Repeated render failure for default template |

## QA Scenario Matrix

1. Invalid feed URL -> actionable message and retry path.
2. Too-frequent schedule/invalid recipients -> submit blocked with remediation text.
3. Delete + undo window (single + bulk) -> reversible actions visible and functional.
4. Failed run notification -> deep link opens Activity run details.
5. Delivery status failure -> filterable in Reports and jump actions available.

## Recovery Validation Gate

Run from `apps/packages/ui`:

```bash
bunx vitest run \
  src/components/Option/Watchlists/shared/__tests__/watchlists-error.test.ts \
  src/components/Option/Watchlists/shared/__tests__/watchlists-error.locale-contract.test.ts \
  src/components/Option/Watchlists/SourcesTab/__tests__/SourceFormModal.test-source.test.tsx \
  src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.delete-confirm.test.tsx \
  src/components/Option/Watchlists/SourcesTab/__tests__/source-undo.test.ts \
  src/components/Option/Watchlists/JobsTab/__tests__/JobFormModal.live-summary.test.tsx \
  src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx \
  src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.accessibility-live-region.test.tsx \
  src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.run-notifications.test.tsx
```

## Monitoring Thresholds

Create an incident ticket when one threshold is breached for two consecutive release candidates:

- Run failures/stalls exceed 20% of run attempts.
- Output delivery failures exceed 10% of generated reports.
- Recovery gate regressions block user remediation flows.

## Evidence for Release Candidate

- Recovery gate output.
- Screenshots/log excerpts for each failure-class scenario.
- Linked remediation issues and owner assignment.
