# Watchlists Onboarding First-Value Runbook (2026-02-24)

Date: 2026-02-24  
Owners: Mike (Assignee), Robert (Reviewer)  
Scope: Beginner and advanced onboarding paths from first launch to first successful run/report

## Purpose

Provide a repeatable QA and product-demo checklist for onboarding outcomes:
- first setup completion,
- first run success,
- first report success,
- path-specific friction detection.

## Preconditions

- Watchlists opens from `/options/watchlists` without API/auth errors.
- At least one valid feed URL is available for setup.
- Templates API is reachable (`briefing_md` baseline template available).

## Path A: Beginner (Guided Setup)

1. Open Watchlists Overview.
2. Confirm onboarding mode is `Beginner (guided)`.
3. Start `Guided quick setup`.
4. Complete feed step with one valid feed URL.
5. Complete monitor step using schedule preset (no advanced fields required).
6. Complete review step and create setup.
7. Validate destination:
- `Activity` when `Run immediately` is enabled.
- `Reports` when briefing goal is selected without immediate run.
- `Monitors` when triage goal is selected without immediate run.

Expected result:
- setup completion is successful without cron/Jinja2 requirements,
- quick setup telemetry milestones are recorded,
- first-value surface is immediately reachable.

## Path B: Advanced (Direct Forms)

1. Open Watchlists Overview.
2. Switch onboarding mode to `Advanced (direct forms)`.
3. Use direct CTA to open `Feeds` or `Monitors`.
4. Create one feed and one monitor from direct forms.
5. Trigger run manually from `Activity` or monitor action.
6. Validate first output appears in `Reports`.

Expected result:
- advanced users bypass wizard friction,
- direct path still reaches first run and first report.

## Telemetry Checkpoints

Telemetry module:
- `apps/packages/ui/src/utils/watchlists-onboarding-telemetry.ts`

Expected events:
- `quick_setup_opened`
- `quick_setup_step_completed`
- `quick_setup_completed`
- `first_run_succeeded`
- `first_output_succeeded`

## Regression Commands

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui
bunx vitest run src/components/Option/Watchlists/OverviewTab/__tests__/OverviewTab.quick-setup.test.tsx src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.help-links.test.tsx src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.run-notifications.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx --maxWorkers=1 --no-file-parallelism
bunx vitest run src/utils/__tests__/watchlists-onboarding-telemetry.test.ts --maxWorkers=1 --no-file-parallelism
```

## Release Gate

Do not close onboarding validation if any are true:
- quick setup cannot complete in beginner path without advanced syntax knowledge,
- first run or first output milestone is missing from telemetry after successful flow,
- guided and advanced paths route to incorrect destination surfaces.
