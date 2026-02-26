# Watchlists Scale Readiness Runbook (2026-02-24)

## Purpose

Define the minimum scale-validation gate for Watchlists UX before release candidates, with explicit UC1/UC2 checks, known limits, and mitigation actions.

## Mandatory Gate

Run this command before merging Watchlists scale-sensitive UI changes:

```bash
cd apps/packages/ui && bun run test:watchlists:scale
```

Release candidate rule:
- Block release if this gate fails.
- Block release if known-constraint mitigations below are violated without updated evidence.

## Scale Profiles

| Profile | Feeds | Monitors | Activity Rows | Article Volume | Expected UX Behavior |
|---|---:|---:|---:|---:|---|
| Small | 5 | 5 | <= 100 | <= 500 | No visible delays; immediate triage feedback |
| Analyst | 50 | 20 | <= 2,000 | <= 20,000 | Responsive filters, stable polling, manageable notifications |
| High | 200 | 50 | >= 5,000 | >= 100,000 | No hard UI cliffs; progress + recovery required for bulk actions |

## UC Validation Checklist

### UC1 (Feed Aggregation and Triage)

1. Feeds + monitors load and filter without client-side hard caps.
2. Activity filtering with monitor+status still surfaces matches beyond first API page.
3. Articles triage supports bulk mark-reviewed with:
   - live progress,
   - terminal summary,
   - retry for failed IDs only.
4. Activity auto-refresh does not run while Activity tab is inactive or page is hidden.

### UC2 (Automated Briefing Delivery)

1. Runs/notifications do not spam duplicate terminal events when polling requests overlap.
2. Completion-only notification noise is suppressed while user is in Activity-focused context.
3. Monitor-to-output flow remains navigable under high event volume (grouped notification deep-link still opens newest run).

## Known Constraints and Mitigations

1. Constraint: Notification polling can overlap under short intervals and produce duplicate work.
   Mitigation: in-flight dedup guard in Watchlists notification poller.

2. Constraint: Activity polling can continue in background tabs after user leaves Activity.
   Mitigation: gate polling to active + visible Activity context.

3. Constraint: Bulk triage can partially fail for large item sets.
   Mitigation: persist terminal progress summary and provide retry entrypoint for failed IDs.

4. Constraint: High-volume notification streams can overwhelm users.
   Mitigation: kind-based grouping + completion suppression in low-signal contexts.

## Validation Evidence (2026-02-24)

- `bunx vitest run src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.advanced-filters.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/run-notifications.test.ts src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.run-notifications.test.tsx --maxWorkers=1 --no-file-parallelism`
- `bun run test:watchlists:scale`
- `/tmp/bandit_watchlists_group10_stage4_2026_02_24.json`

## Owner and Review Cadence

- Owner: Watchlists UX assignee for Group 10.
- Trigger for rerun: any change under `apps/packages/ui/src/components/Option/Watchlists/**` that touches polling, notifications, list filtering, or batch operations.
