# Watchlists IA Navigation and Adoption Playbook (2026-02-23)

## Purpose

Operationalize Group 01 IA changes for engineering, QA, and product teams with:

- a canonical navigation map
- a vocabulary matrix (UI labels vs implementation nouns)
- a repeatable QA checklist
- an adoption baseline and post-change comparison framework

## Navigation Map

| User Task | Primary Surface | Next Surface | Outcome |
|---|---|---|---|
| Set up intake | Feeds (`sources`) | Monitors (`jobs`) | Source collection scope is defined. |
| Configure execution | Monitors (`jobs`) | Activity (`runs`) | Scheduled runs start and produce run logs/status. |
| Validate collection | Activity (`runs`) | Articles (`items`) | Captured content is triaged. |
| Review content | Articles (`items`) | Reports (`outputs`) | Briefing-relevant content is promoted to outputs. |
| Validate delivery | Reports (`outputs`) | Templates (`templates`) / Monitors (`jobs`) | Formatting and run preferences are refined for next cycle. |

## Vocabulary Matrix

| Internal/System Noun | Canonical User Label | Where It Appears |
|---|---|---|
| `sources` | Feeds | Tab label, quick actions, orientation guidance, Overview cards |
| `jobs` | Monitors | Tab label, quick actions, orientation guidance, Overview cards |
| `runs` | Activity | Tab label, quick actions, orientation guidance, notifications |
| `items` | Articles | Tab label, quick actions, orientation guidance, Overview cards |
| `outputs` | Reports | Tab label, quick actions, orientation guidance, output list/detail |
| `templates` | Templates | Tab label, orientation guidance |
| `settings` | Settings | Tab label, orientation guidance |

## QA Checklist (IA + Navigation)

### Primary Journey Checks

1. From Overview, use orientation actions to reach Feeds then Monitors.
2. From Monitors, use orientation action to open Activity.
3. From Activity, use orientation action to open Reports.
4. From Articles, use orientation action to open Monitors.
5. Verify cross-tab state changes without dead-end screens.

### Label and Terminology Checks

1. Tabs consistently display canonical labels: Feeds, Monitors, Activity, Articles, Reports.
2. Quick actions and orientation actions use the same canonical labels.
3. Context docs link text uses tab-aligned labels (`Learn more: <tab guidance>`).

### Help Routing Checks

1. Main docs link points to `WATCHLISTS_MAIN_DOCS_URL`.
2. Context docs link routes by active tab (`WATCHLISTS_TAB_HELP_DOCS` mapping).
3. Issue-report link points to `WATCHLISTS_ISSUE_REPORT_URL`.

## Adoption Metrics Baseline and Comparison

### Baseline Inputs (Current)

Source: `Docs/Plans/watchlists_ux_stage1_telemetry_export_2026_02_23.md`

| Metric | Baseline |
|---|---:|
| UC1-F1 First source setup | 92.96% (66/71) |
| UC1-F2 Time-to-first-review (median) | 567.49s |
| UC1-F3 Triage completion (>=20/day) | 0.00% (0/2) |
| UC2-F1 Source->job->run completion | 56.72% (38/67) |
| UC2-F2 Text output success | 0.06% (2/3182) |
| UC2-F3 Audio output success | 0.03% (1/3182) |

### IA Variant Adoption Metrics

Source endpoint: `GET /api/v1/watchlists/telemetry/ia-experiment/summary`

Track and compare baseline vs experimental:

- `sessions`
- `reached_target_sessions`
- `avg_transitions`
- `avg_visited_tabs`
- `avg_session_seconds`

### Post-Change Comparison Template

| Metric | Baseline Variant | Experimental Variant | Delta | Status |
|---|---:|---:|---:|---|
| avg_transitions | TBD | TBD | `(exp - base) / base` | Pass/Fail |
| avg_visited_tabs | TBD | TBD | `(exp - base) / base` | Pass/Fail |
| reached_target_sessions | TBD | TBD | absolute | Pass/Fail |
| UC1-F2 median seconds | 567.49 | TBD | `% change` | Monitor |
| UC2-F1 completion rate | 56.72% | TBD | `pp change` | Monitor |

Use go/no-go thresholds defined in:

- `Docs/Plans/WATCHLISTS_IA_EXPERIMENT_ROLLOUT_GONOGO_2026_02_23.md`

## Stage 5 Regression Gate

Run from `apps/packages/ui`:

```bash
bunx vitest run \
  src/components/Option/Watchlists/shared/__tests__/help-docs.test.ts \
  src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.help-links.test.tsx \
  src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.experimental-ia.test.tsx \
  src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.orientation-guidance.test.tsx \
  src/components/Option/Watchlists/__tests__/watchlists-terminology-contract.test.ts \
  src/components/Option/Watchlists/__tests__/watchlists-plain-language-copy-contract.test.ts \
  src/routes/__tests__/option-watchlists.route-state.test.tsx \
  src/utils/__tests__/watchlists-ia-experiment-telemetry.test.ts \
  src/utils/__tests__/watchlists-ia-rollout.test.ts
```
