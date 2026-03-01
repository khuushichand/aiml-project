# Watchlists UC2 Pipeline KPI Runbook (Group 03 Stage 5)

Date: 2026-02-24  
Owners: Robert (Assignee), Mike (Reviewer)  
Scope: UC2 pipeline builder funnel reliability and first-success validation

## Purpose

Define a repeatable validation flow for the Overview pipeline builder so product and QA can measure:
- setup completion,
- step-level abandonment,
- first run success,
- first report success.

This runbook uses the existing onboarding metrics module in:
`apps/packages/ui/src/utils/watchlists-onboarding-telemetry.ts`

## UC2 Event Contract

The UC2 funnel is captured by these event types:

| Event | Meaning |
|---|---|
| `pipeline_setup_opened` | User opened the pipeline builder modal. |
| `pipeline_setup_step_completed` | User completed `scope`, `briefing`, or `review` step validation. |
| `pipeline_setup_preview_generated` | Template preview result (`success`, `empty`, `no_run_context`, `template_empty`, `error`). |
| `pipeline_setup_submitted` | User submitted pipeline creation (`mode=create|test`, `runNow`). |
| `pipeline_setup_completed` | Pipeline setup succeeded (`destination=jobs|outputs`). |
| `pipeline_setup_failed` | Setup failed with stage (`validation`, `job_create`, `run_trigger`, `output_create`, `rollback`). |
| `first_run_succeeded` | First successful run milestone reached. |
| `first_output_succeeded` | First successful output milestone reached. |

## KPI Definitions

Use `buildWatchlistsUc2PipelineDashboardSnapshot(...)` to produce KPI values.

| KPI ID | Metric | Formula |
|---|---|---|
| UC2-P1 | Setup completion rate | `pipeline_setup_completed / pipeline_setup_opened` |
| UC2-P2 | Completion from submission | `pipeline_setup_completed / pipeline_setup_submitted` |
| UC2-P3 | First run success rate | `first_run_succeeded / pipeline_setup_completed` |
| UC2-P4 | First output success rate | `first_output_succeeded / pipeline_setup_completed` |
| UC2-P5 | Step drop-off | `opened->scope`, `scope->briefing`, `briefing->review`, `review->submitted`, `submitted->completed` |

## Baseline Context (Stage 1 Export)

Source: `Docs/Plans/watchlists_ux_stage1_telemetry_export_2026_02_23.md`

- UC2-F1 Pipeline completion: 56.72% (38/67)
- UC2-F2 Text output success: 0.06% (2/3182 completed runs)
- UC2-F3 Audio output success: 0.03% (1/3182 completed runs)

## QA Validation Scenarios

| Scenario ID | Scenario | Expected Result |
|---|---|---|
| UC2-03-01 | Happy path (run now) | `pipeline_setup_completed` with `destination=outputs`; first-success milestones eventually present. |
| UC2-03-02 | Save without run now | `pipeline_setup_completed` with `destination=jobs`; no immediate run/output dependency. |
| UC2-03-03 | Preview without completed run | `pipeline_setup_preview_generated` with `status=no_run_context`. |
| UC2-03-04 | Run trigger failure | `pipeline_setup_failed` with `stage=run_trigger`; rollback path recorded if needed. |
| UC2-03-05 | Test generation flow | `pipeline_setup_submitted` and `pipeline_setup_completed` with `mode=test`. |

## Demo Flow (Product)

1. Open Overview -> select `Briefing pipeline builder`.
2. Complete scope and briefing steps.
3. In review, run `Generate preview`.
4. Use `Run test generation`.
5. Confirm Activity/Reports linkage and KPI snapshot values.

## Inspection Snippet

```ts
import {
  getWatchlistsOnboardingTelemetryState,
  buildWatchlistsUc2PipelineDashboardSnapshot
} from "@/utils/watchlists-onboarding-telemetry"

const state = await getWatchlistsOnboardingTelemetryState()
const snapshot = buildWatchlistsUc2PipelineDashboardSnapshot(state)
console.log(snapshot)
```

## Validation Commands

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui
bunx vitest run src/utils/__tests__/watchlists-onboarding-telemetry.test.ts src/components/Option/Watchlists/OverviewTab/__tests__/OverviewTab.quick-setup.test.tsx src/components/Option/Watchlists/OverviewTab/__tests__/pipeline-contract.test.ts --maxWorkers=1 --no-file-parallelism
bunx vitest run src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.run-notifications.test.tsx src/components/Option/Watchlists/OutputsTab/__tests__/OutputsTab.advanced-filters.test.tsx --maxWorkers=1 --no-file-parallelism
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r apps/packages/ui/src/components/Option/Watchlists/OverviewTab apps/packages/ui/src/utils -f json -o /tmp/bandit_watchlists_group03_stage5_2026_02_24.json
```
