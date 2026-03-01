# Watchlists Scale Profile Baseline (2026-02-23)

## Load Profiles

- `Small`: 5 feeds, 3 monitors, <=200 items/day.
- `Medium`: 50 feeds, 15 monitors, <=2,000 items/day.
- `Large`: 200 feeds, 50 monitors, <=10,000 items/day.
- `Burst notifications`: up to 1,000 run-state events in a poll cycle.

## Baseline Timing Capture

Captured via:

- `apps/packages/ui/src/components/Option/Watchlists/__tests__/watchlists-scale-baseline.bench.test.ts`

Command:

```bash
bunx vitest run src/components/Option/Watchlists/__tests__/watchlists-scale-baseline.bench.test.ts
```

Observed timings (local baseline run on 2026-02-23):

- Source filter + order pipeline:
  - 5 feeds: `5.08ms` (first-run warmup outlier)
  - 50 feeds: `0.06ms`
  - 200 feeds: `0.10ms`
- Items sort pipeline:
  - 100 items: `0.13ms`
  - 1,000 items: `1.73ms`
  - 5,000 items: `6.66ms`
- Run notification dedupe + grouping (1,000 events): `0.33ms`

## Stage-1 Performance Budgets

- Sources sidebar filter+ordering pipeline:
  - Budget: `<60ms` for 200 feeds.
- Items sort pipeline:
  - Budget: `<300ms` for 5,000 items.
- Run-notification dedupe/group pipeline:
  - Budget: `<80ms` for 1,000 events.
- Interaction budget targets (to enforce in subsequent stages):
  - Filter toggle to visible list update: `<150ms` perceived response.
  - Modal/drawer open to actionable focus: `<200ms`.
  - Poll-driven live status update announcement: `<250ms` after payload receipt.

## Priority Bottlenecks and Constraints

- Sources tab still uses dataset fetches for some client-side filtering scenarios; high-cardinality workspaces may incur API overhead before UI transforms.
- Jobs/Runs/Outputs tables are not virtualized; pagination is the current mitigation for DOM growth.
- Items reader selection and batch operations are responsive in baseline tests, but end-to-end high-volume fetch latency remains API-bound.
- Notification polling now uses adaptive cadence and payload sizing with in-flight overlap protection; backend-side event burst throttling remains a potential follow-up for extreme workloads.

## Operational Runbook

- Scale release and monitoring runbook:
  - `Docs/Plans/WATCHLISTS_SCALE_READINESS_RUNBOOK_2026_02_23.md`
