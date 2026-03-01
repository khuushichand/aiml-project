# Watchlists Post-Release Monitoring Plan (2026-02-24)

Date: 2026-02-24  
Program owner: Robert  
Reviewer: Mike  
Scope: UC1 and UC2 stabilization thresholds after UX remediation rollout

## Purpose

Define active monitoring thresholds and ownership for Watchlists post-release stabilization.

## Monitoring Sources

- Onboarding and UC2 KPI telemetry:
  - `apps/packages/ui/src/utils/watchlists-onboarding-telemetry.ts`
  - `Docs/Plans/WATCHLISTS_UC2_PIPELINE_KPI_RUNBOOK_2026_02_24.md`
- Recovery/error taxonomy guidance:
  - `Docs/Plans/WATCHLISTS_RECOVERY_RUNBOOK_2026_02_23.md`
- Accessibility acceptance gate:
  - `.github/workflows/ui-watchlists-a11y-gates.yml`
- Scale acceptance gate:
  - `.github/workflows/ui-watchlists-scale-gates.yml`

## Operational Thresholds

| ID | Signal | Threshold | Action |
|---|---|---|---|
| MON-UC2-01 | UC2 setup completion rate | `< 0.50` for 3 consecutive daily snapshots | Trigger UX regression triage for pipeline builder steps. |
| MON-UC2-02 | UC2 first output success rate | `< 0.40` per completed setup cohort | Review run/output failure mix and template defaults. |
| MON-UC2-03 | Pipeline run-trigger failures | `> 10%` of pipeline submissions/day | Escalate to backend scheduling/run queue diagnostics. |
| MON-ERR-01 | Recovery-category error spikes | `> 2x` baseline for auth/timeout/network categories | Run recovery runbook incident procedure. |
| MON-A11Y-01 | Watchlists accessibility gate | Any CI failure on `test:watchlists:a11y` | Block release candidate; fix before merge. |
| MON-SCALE-01 | Watchlists scale gate | Any CI failure on `test:watchlists:scale` | Block release candidate; profile and remediate. |

## Ownership and Escalation

| Area | Primary | Secondary | Escalation SLA |
|---|---|---|---|
| Onboarding/UC2 funnel drops | Mike | Robert | Same business day |
| Run/output reliability failures | Robert | Mike | Same business day |
| Accessibility gate regressions | Robert | Mike | Immediate release block |
| Scale gate regressions | Mike | Robert | Immediate release block |

## Weekly Cadence

1. Review UC2 KPI snapshot (`completionPerOpened`, `firstOutputPerCompleted`, failure-stage counters).
2. Review runbook scenario pass rates for onboarding, recovery, scale, and accessibility.
3. Confirm CI Watchlists gates remained green for the full week.
4. Record any threshold breaches and remediation issue links in the weekly engineering note.

## Active Gate Commands

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui
bun run test:watchlists:help
bun run test:watchlists:a11y
bun run test:watchlists:scale
```
