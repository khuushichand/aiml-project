# Watchlists Onboarding Effectiveness Validation Runbook (2026-02-23)

## Purpose

Define the Stage 5 validation contract for first-run onboarding effectiveness (Group 02), including milestone telemetry, time-to-value metrics, drop-off rates, and QA checks for beginner and power paths.

## Baseline Funnel Inputs (Stage 1 Export)

Source: `Docs/Plans/watchlists_ux_stage1_telemetry_export_2026_02_23.md`

| Funnel Metric | Baseline | Numerator / Denominator |
|---|---:|---:|
| UC1-F1 First source setup | 92.96% | 66 / 71 users |
| UC1-F2 Time-to-first-review (median) | 567.49s | samples=1 |
| UC1-F3 Triage completion (>=20/day) | 0.00% | 0 / 2 users |
| UC2-F1 Pipeline completion (source->job->run) | 56.72% | 38 / 67 users |
| UC2-F2 Text output success | 0.06% | 2 / 3182 completed runs |
| UC2-F3 Audio output success | 0.03% | 1 / 3182 completed runs |

## Stage 5 Telemetry Contract

Implementation:

- `apps/packages/ui/src/utils/watchlists-onboarding-telemetry.ts`
- `buildWatchlistsUc2FunnelDashboardSnapshot(...)`

Backend API source of truth:

- `POST /api/v1/watchlists/telemetry/onboarding` (best-effort event ingest from frontend milestones)
- `GET /api/v1/watchlists/telemetry/onboarding/summary` (user-scoped onboarding counters/rates/timings)
- `GET /api/v1/watchlists/telemetry/rc-summary` (onboarding + IA + backend UC2 run/output truth for RC reporting)

RC automation:

- Workflow: `.github/workflows/ui-watchlists-telemetry-rc-report.yml`
- Trigger: `push` on `release/**` + `rc/**`, and `workflow_dispatch`
- Threshold semantics: reporting-only (`ok|potential_breach` rows do not fail workflow)
- Failure policy: workflow failure means operational error only (startup/fetch/script execution)

Primary onboarding milestones:

- `quick_setup_opened` (setup start)
- `quick_setup_completed` (setup completion)
- `quick_setup_first_run_succeeded`
- `quick_setup_first_output_succeeded`

Milestone signal sources:

- Overview refresh (`source: "overview"`)
- Reports load (`source: "outputs"`)
- Run transition polling (`source: "run_notifications"`)

## KPI Definitions

Rates from `buildWatchlistsUc2FunnelDashboardSnapshot(...)`:

- `setupCompletionRate = quick_setup_completed / quick_setup_opened`
- `firstRunSuccessRate = first_run_success / briefing_completions`
- `firstOutputSuccessRate = first_output_success / briefing_completions`
- `setupDropoffRate = 1 - setupCompletionRate`
- `runSuccessDropoffRate = 1 - firstRunSuccessRate`
- `outputSuccessDropoffRate = 1 - firstOutputSuccessRate`

TTTV metrics (median seconds):

- `medianSecondsToSetupCompletion`
- `medianSecondsToFirstRunSuccess`
- `medianSecondsToFirstOutputSuccess`

Notes:

- TTTV metrics are built from local onboarding sample queues and represent onboarding progression timing, not backend run SLA.
- Backend UC2-F2/UC2-F3 exports remain release truth for output reliability.

## Regression Gates

Run from `apps/packages/ui`:

```bash
bun run test:watchlists:onboarding
bun run test:watchlists:uc2
```

`test:watchlists:onboarding` includes telemetry schema checks plus onboarding happy-path and interruption-recovery flows.

## QA Checklist

### Beginner Path (Guided Setup)

1. Open guided setup, complete feed + monitor + review.
2. Confirm setup completion event is recorded.
3. Enable run-now and verify first run transition is captured.
4. Verify first output milestone is captured once reports become available.

### Beginner Path (Interruption Recovery)

1. Open guided setup, enter feed details, advance to review.
2. Force candidate preview failure and confirm setup remains actionable.
3. Complete setup after interruption and verify completion + success milestones.

### Power Path (Direct Actions)

1. Use direct Add Feed/Create Monitor actions instead of guided tour.
2. Trigger monitor run from Activity/Monitors.
3. Verify first run and first output milestones are still captured via run polling and reports load.

## Monitoring Thresholds

Trigger investigation if either condition persists for two release candidates:

- `setupCompletionRate` drops by >=10 percentage points.
- `firstOutputSuccessRate` drops by >=10 percentage points.
- `medianSecondsToFirstOutputSuccess` regresses by >=25% without an accepted operational incident note.

## Evidence Template

For each release candidate:

- Output from `bun run test:watchlists:onboarding`.
- Output from `bun run test:watchlists:uc2`.
- `UI Watchlists Telemetry RC Report` step summary + artifact (`watchlists-telemetry-rc-report`).
- Current snapshot values from `buildWatchlistsUc2FunnelDashboardSnapshot(...)`.
- Updated baseline comparison against Stage 1 export.
- Incident/remediation links for any breached thresholds.
