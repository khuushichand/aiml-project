# Watchlists Scale Profiles and Performance Budgets (2026-02-24)

## Stage 1 Scope

Group 10 Stage 1 baseline for scale readiness:

- Define representative load profiles (`small`, `team`, `large`)
- Define per-surface performance budgets (render, interaction, refresh cadence)
- Capture baseline render/mutation timing samples with a repeatable harness

## Load Profiles

| Profile | Feeds | Monitors | Runs | Items | Target Use Case |
|---|---:|---:|---:|---:|---|
| `small` | 5 | 5 | 25 | 250 | Individual researcher |
| `team` | 50 | 25 | 200 | 2,000 | Analyst team |
| `large` | 200 | 75 | 600 | 8,000 | High-volume deployment |

## Per-Surface Budgets

| Surface | Render Latency (ms) | Interaction Latency (ms) | Refresh Cadence (s) |
|---|---:|---:|---:|
| Overview | 100 | 60 | 180 |
| Feeds | 140 | 90 | 300 |
| Monitors | 150 | 100 | 300 |
| Activity | 130 | 90 | 120 |
| Articles | 180 | 120 | 60 |
| Reports | 140 | 90 | 180 |

## Baseline Timing Samples (Median of 5 post-warm runs)

Timings captured from `runWatchlistsScaleBenchmark()` (render + mutation paths):

| Operation | Small (ms) | Team (ms) | Large (ms) |
|---|---:|---:|---:|
| `feedsRenderPrepMs` | 0.01 | 0.02 | 0.08 |
| `feedsSearchMutationMs` | 0.00 | 0.01 | 0.02 |
| `monitorsRenderPrepMs` | 0.04 | 0.04 | 0.03 |
| `monitorsToggleMutationMs` | 0.00 | 0.01 | 0.01 |
| `activityRenderPrepMs` | 0.01 | 0.01 | 0.03 |
| `articlesRenderPrepMs` | 0.08 | 0.51 | 2.26 |
| `articlesBatchMutationMs` | 0.02 | 0.06 | 0.11 |

Observed hotspot trend: `articlesRenderPrepMs` scales fastest and remains the primary bottleneck candidate.

## Known Constraints

- Harness currently measures client-side preparation/mutation logic, not full DOM paint or network latency.
- Baseline values are environment-dependent and should be treated as comparative indicators, not absolute SLA proofs.
- `reports` surface budget is defined at Stage 1 but is not yet covered by this harness; add explicit reports operations in Group 10 Stage 2.

## Reproduction

```bash
cd apps/packages/ui
bun run test:watchlists:scale
```

Optional baseline sampling command:

```bash
cd apps/packages/ui
bun -e "import { runWatchlistsScaleBenchmark } from './src/components/Option/Watchlists/shared/scale-benchmark.ts'; const keys=['small','team','large']; for (const key of keys) console.log(key, runWatchlistsScaleBenchmark(key));"
```
