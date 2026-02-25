# Watchlists UC2 Workflow KPI Runbook (2026-02-23)

## Purpose

Define the operational KPI contract for UC2 (feed setup -> monitor schedule -> first briefing output), including local onboarding telemetry milestones and release-gate regression coverage.

## Baseline Funnel Snapshot (Telemetry Export)

Source: `Docs/Plans/watchlists_ux_stage1_telemetry_export_2026_02_23.md`

| Funnel Metric | Baseline | Numerator / Denominator |
|---|---:|---:|
| UC2-F1 Pipeline completion (source -> job -> run) | 56.72% | 38 / 67 users |
| UC2-F2 Text output success | 0.06% | 2 / 3182 completed runs |
| UC2-F3 Audio output success | 0.03% | 1 / 3182 completed runs |

## Stage 5 KPI Contract (Frontend Telemetry)

Telemetry implementation:

- `apps/packages/ui/src/utils/watchlists-onboarding-telemetry.ts`
- `buildWatchlistsUc2FunnelDashboardSnapshot(...)`

Primary UC2 onboarding event milestones:

- `quick_setup_opened`
- `quick_setup_step_completed` (`feed`, `monitor`, `review`)
- `quick_setup_preview_loaded` (`candidate`, `template`)
- `quick_setup_preview_failed` (`candidate`, `template`)
- `quick_setup_test_run_triggered`
- `quick_setup_test_run_failed`
- `quick_setup_first_run_succeeded`
- `quick_setup_first_output_succeeded`
- `quick_setup_completed` (`destination`: `runs` | `outputs` | `jobs`)
- `quick_setup_failed`

Dashboard snapshot rates:

- `setupCompletionRate`: `quick_setup_completed / quick_setup_opened`
- `briefingCompletionRate`: `briefing completions / quick_setup_completed`
- `runNowOptInRate`: `completed_with_run_now / briefing completions`
- `testRunTriggerRate`: `test_run_triggered / completed_with_run_now`
- `firstSuccessProxyRate`: `test_run_triggered / briefing completions`
- `firstRunSuccessRate`: `first_run_success / briefing completions`
- `firstOutputSuccessRate`: `first_output_success / briefing completions`
- `setupDropoffRate`: `1 - setupCompletionRate`
- `runSuccessDropoffRate`: `1 - firstRunSuccessRate`
- `outputSuccessDropoffRate`: `1 - firstOutputSuccessRate`

Dashboard snapshot timing metrics:

- `medianSecondsToSetupCompletion`
- `medianSecondsToFirstRunSuccess`
- `medianSecondsToFirstOutputSuccess`

Note: `firstSuccessProxyRate` remains a frontend proxy. `firstRunSuccessRate` and `firstOutputSuccessRate` are milestone-based onboarding outcomes. Backend run/output success remains the source of truth for release baselines (UC2-F2/UC2-F3 above).

Backend telemetry source endpoints:

- `POST /api/v1/watchlists/telemetry/onboarding`
- `GET /api/v1/watchlists/telemetry/onboarding/summary`
- `GET /api/v1/watchlists/telemetry/rc-summary`

RC telemetry report automation:

- Workflow: `.github/workflows/ui-watchlists-telemetry-rc-report.yml`
- Trigger: `push` on `release/**` + `rc/**`, and `workflow_dispatch`
- Threshold policy: reporting-only (`ok|potential_breach`)
- Failure policy: operational errors only (not threshold breaches)

## Release Gate (Automated)

Run from `apps/packages/ui`:

```bash
bun run test:watchlists:uc2
```

Gate definition location:

- `apps/packages/ui/package.json`

## Release Gate (Manual Smoke)

1. Start from a clean first-run state and complete quick setup with `briefing` + `run now`.
2. Confirm review step shows both candidate preview summary and template preview.
3. Confirm quick setup routes to Activity run detail when `run now` is enabled.
4. Repeat with `run now` disabled and confirm route to Reports.
5. Confirm preview failure path still allows setup completion and exposes retry guidance.

## Monitoring Thresholds (Post-Release)

Trigger UC2 workflow investigation if either condition persists for two consecutive release candidates:

- `setupCompletionRate` decreases by >=10 percentage points vs prior release candidate.
- `firstOutputSuccessRate` decreases by >=10 percentage points vs prior release candidate.
- `medianSecondsToFirstOutputSuccess` regresses by >=25% vs prior release candidate.
- Backend UC2-F2 or UC2-F3 drops below existing baseline without an accepted migration/incident note.

## Evidence Capture Template

For each release candidate, capture:

- Output from `bun run test:watchlists:uc2`.
- Output from `bun run test:watchlists:onboarding` (shared onboarding milestone gate).
- `UI Watchlists Telemetry RC Report` markdown summary and JSON artifact.
- Current `buildWatchlistsUc2FunnelDashboardSnapshot(...)` export values.
- Latest backend UC2-F1/F2/F3 export reference path.
- Any threshold breaches and remediation ticket links.
