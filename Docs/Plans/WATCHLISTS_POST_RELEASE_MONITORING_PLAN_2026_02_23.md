# Watchlists Post-Release Monitoring Plan (2026-02-23)

## Purpose

Consolidate post-release monitoring for onboarding quality, workflow reliability, accessibility, and scale readiness after UX remediation rollout.

## Active Gates

Run from `apps/packages/ui`:

```bash
bun run test:watchlists:program
```

Expanded gate chain:

- `test:watchlists:help`
- `test:watchlists:onboarding`
- `test:watchlists:uc2`
- `test:watchlists:a11y`
- `test:watchlists:scale`

## RC Automation

- Dedicated workflow: `.github/workflows/ui-watchlists-rc-gate.yml`
- Dedicated telemetry workflow: `.github/workflows/ui-watchlists-telemetry-rc-report.yml`
- Trigger modes: `push` to `release/**` and `rc/**`, plus `workflow_dispatch`
- Decision policy: any failed Watchlists gate yields `NO-GO` and blocks RC promotion
- Telemetry policy: threshold states are reporting-only (`ok|potential_breach`); workflow fails only for operational errors (server startup/fetch/script failures)
- Telemetry source endpoint: `GET /api/v1/watchlists/telemetry/rc-summary`
- Operator guide: `Docs/Plans/WATCHLISTS_RC_OPERATIONS_RUNBOOK_2026_02_23.md`

## Metric and Threshold Matrix

| Domain | Key Metrics | Investigation Threshold |
|---|---|---|
| Onboarding (Group 02) | `setupCompletionRate`, `firstOutputSuccessRate`, `medianSecondsToFirstOutputSuccess` | `setupCompletionRate` or `firstOutputSuccessRate` drop >=10pp for 2 RCs, or median first-output timing regresses >=25% |
| UC2 Workflow (Group 03) | `briefingCompletionRate`, `firstRunSuccessRate`, `firstOutputSuccessRate` | first-output success drop >=10pp for 2 RCs |
| Recovery (Group 05) | run failure/stall %, delivery failure %, recovery gate regressions | run failures/stalls >20% or delivery failures >10% for 2 RCs |
| Accessibility (Group 09) | a11y regression gate pass/fail, focus/live-region smoke checks | any accessibility gate regression blocks release candidate |
| Scale (Group 10) | scale gate pass/fail, adaptive polling overlap checks, high-volume UI latency regressions | scale gate regression or adaptive-polling overlap regression blocks release candidate |
| IA/Navigation (Group 01) | IA experiment adoption metrics and tab-transition telemetry | go/no-go thresholds breached per IA rollout runbook |

## Runbook Sources

- `Docs/Plans/WATCHLISTS_IA_EXPERIMENT_ROLLOUT_GONOGO_2026_02_23.md`
- `Docs/Plans/WATCHLISTS_IA_NAVIGATION_ADOPTION_PLAYBOOK_2026_02_23.md`
- `Docs/Plans/WATCHLISTS_ONBOARDING_EFFECTIVENESS_VALIDATION_RUNBOOK_2026_02_23.md`
- `Docs/Plans/WATCHLISTS_UC2_WORKFLOW_KPI_RUNBOOK_2026_02_23.md`
- `Docs/Plans/WATCHLISTS_RECOVERY_RUNBOOK_2026_02_23.md`
- `Docs/Plans/WATCHLISTS_ACCESSIBILITY_GOVERNANCE_RUNBOOK_2026_02_23.md`
- `Docs/Plans/WATCHLISTS_SCALE_READINESS_RUNBOOK_2026_02_23.md`
- `Docs/Plans/WATCHLISTS_RC_OPERATIONS_RUNBOOK_2026_02_23.md`

## Operational Cadence

1. Per release candidate: confirm both `UI Watchlists RC Gate` and `UI Watchlists Telemetry RC Report` workflow results and review generated summaries/artifacts.
2. Weekly: review onboarding/UC2 milestone trend snapshots against baselines.
3. Bi-weekly: review accessibility and scale gate reliability trend.
4. Incident-driven: create remediation ticket when thresholds are breached twice consecutively.

## Ownership

- Primary execution owner: assignee of active release candidate.
- Review owner: designated reviewer in program coordination ledger.
- Escalation: open blocking issue when any hard gate fails or threshold breach persists for 2 RCs.
