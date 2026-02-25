# Watchlists Scale Readiness Runbook (2026-02-23)

## Purpose

Certify Watchlists UX readiness for analyst-scale workspaces and define repeatable release gates for UC1 (aggregation/triage) and UC2 (briefing generation and delivery).

## Baseline Funnel Snapshot (Telemetry Export)

Source: `Docs/Plans/watchlists_ux_stage1_telemetry_export_2026_02_23.md`

| Funnel Metric | Baseline | Numerator / Denominator |
|---|---:|---:|
| UC1-F1 First source setup | 92.96% | 66 / 71 users |
| UC1-F2 Time-to-first-review (median) | 567.49s (0.16h) | sample size = 1 |
| UC1-F3 Triage completion (>=20/day) | 0.00% | 0 / 2 users |
| UC2-F1 Pipeline completion (source -> job -> run) | 56.72% | 38 / 67 users |
| UC2-F2 Text output success | 0.06% | 2 / 3182 completed runs |
| UC2-F3 Audio output success | 0.03% | 1 / 3182 completed runs |

## Scale Profiles

- `Small`: 5 feeds, 3 monitors, <=200 items/day.
- `Medium`: 50 feeds, 15 monitors, <=2,000 items/day.
- `Large`: 200 feeds, 50 monitors, <=10,000 items/day.
- `Burst`: up to 1,000 run-notification events in one polling cycle.

## Scale Scenario Matrix

| Scenario ID | Flow | Dataset | Pass Criteria |
|---|---|---|---|
| SC-01 | UC1 source management | 200 feeds | Source table remains selectable for bulk move actions and filter updates stay responsive. |
| SC-02 | UC1 monitor management | 200 monitors | Compact summary rendering remains readable and advanced details remain optional. |
| SC-03 | UC1 article triage | 1,000+ items | Source sidebar progressively renders; selection + all-filtered review remain responsive. |
| SC-04 | UC1 batch recovery | 200+ selected items | Chunked progress updates, terminal summaries, and retry-failed action remain functional. |
| SC-05 | UC2 activity visibility | 500+ runs | Advanced filters and run-status updates remain interactive. |
| SC-06 | UC2 output visibility | 500+ outputs | Advanced filters remain interactive and run-to-output traceability remains intact. |
| SC-07 | UC2 notification burst | 1,000 events | Deduping and grouping remain stable; no overlapping poll requests. |

## Release Gate (Automated)

Run from `apps/packages/ui`:

```bash
bun run test:watchlists:scale
```

Gate definition location:

- `apps/packages/ui/package.json`

## Release Gate (Manual Smoke)

1. Run SC-01/SC-02 from `Docs/Plans/WATCHLISTS_MONITOR_DENSITY_SCALE_QA_CHECKLIST_2026_02_23.md`.
2. Run SC-03/SC-04 from `Docs/Plans/WATCHLISTS_ARTICLES_READER_SCALE_QA_CHECKLIST_2026_02_23.md`.
3. Confirm run notification panel behavior under active and idle browser-tab states.
4. Confirm no regression in "retry failed" batch action after partial failures.

## Known Scale Constraints and Mitigations

| Constraint | Current Mitigation | Residual Risk |
|---|---|---|
| Non-virtualized Jobs/Runs/Outputs tables | Pagination + advanced filters + compact summaries | Very large pages can still increase DOM/memory pressure. |
| Reader source catalog growth | Progressive source sidebar rendering + explicit 1000-source cap hint | Users above cap require tighter source partitioning. |
| High-volume review operations | 20-item chunked batch processing + progress panel + retry-failed action | API latency can still extend completion time at peak load. |
| Notification polling costs | Adaptive interval + adaptive payload size + in-flight overlap guard | Burst-heavy workspaces may still need backend-side event throttling. |

## Monitoring Thresholds (Post-Release)

- Trigger a scale regression investigation if any of these occur in two consecutive release candidates:
  - Scale gate command fails.
  - Source/order pipeline exceeds `60ms` for 200 feeds baseline.
  - Items sort pipeline exceeds `300ms` for 5,000 items baseline.
  - Notification dedupe/grouping exceeds `80ms` for 1,000-event baseline.
  - Batch review partial-failure rate exceeds `5%` during QA high-volume runs.

## Evidence Capture Template

For each release candidate, capture:

- Scale gate command output artifact path.
- Manual scenario checklist completion notes.
- Any threshold breaches and remediation ticket links.
