# Watchlists IA Adoption Validation Checklist (2026-02-24)

## Scope

Group 01 Stage 5 closure artifact for Information Architecture and Navigation.

Goals covered:

1. Navigation map and vocabulary matrix documented.
2. QA checklist for primary IA flows and terminology consistency.
3. Adoption metric baseline and post-change comparison method defined.

## Navigation Map

### Baseline IA (legacy)

| User-facing tab | Primary purpose | Canonical task phase |
|---|---|---|
| Overview | At-a-glance system health and setup entry points | Orientation |
| Feeds | Source CRUD, grouping, import/export | Collect |
| Monitors | Scheduling and processing definition | Collect |
| Activity | Run health, logs, retry/cancel paths | Review |
| Articles | Captured content triage | Review |
| Reports | Generated output list + delivery state | Briefings |
| Templates | Output formatting and prompt composition | Briefings |
| Settings | Workspace-level watchlists controls | Orientation/ops |

### Reduced IA (experimental)

| Primary tabs | Secondary (`More views`) | Task views |
|---|---|---|
| `Overview`, `Feeds`, `Articles`, `Reports`, `Settings` | `Monitors`, `Activity`, `Templates` | `Collect`, `Review`, `Briefings` |

### Orientation Banner Next-Step Contract

| Active surface | Expected next-step actions |
|---|---|
| Overview | Open Feeds, Open Monitors |
| Feeds | Open Monitors, Open Activity |
| Monitors | Open Activity, Open Articles |
| Activity | Open Reports, Open Articles |
| Articles | Open Monitors, Open Reports |
| Reports | Open Templates, Open Activity |
| Templates | Open Monitors, Open Reports |
| Settings | Open Overview, Open Feeds |

## Vocabulary Matrix (System -> User)

| Internal/system term | Canonical user label | Notes |
|---|---|---|
| Sources | Feeds | Input collection endpoints |
| Jobs | Monitors | Scheduling + processing definitions |
| Runs | Activity | Execution history and operational status |
| Items | Articles | Captured content for triage |
| Outputs | Reports | Generated briefing artifacts |

Source of truth:
- `apps/packages/ui/src/assets/locale/en/watchlists.json` (`terminology.canonical`, `terminology.aliases`, `tabs`, `quickActions`, `orientation`)

## QA Checklist (IA + Terminology)

### Primary journey checklist

- [ ] `Overview -> Feeds -> Monitors -> Activity -> Reports` flow is reachable with one explicit action per hop.
- [ ] Orientation banner copy appears for each tab with expected next-step actions.
- [ ] `Activity -> Reports` transition is available and uses outcome language (`Open Reports`).
- [ ] `Articles -> Monitors` transition is available and uses outcome language (`Open Monitors`).

### Experimental IA safety checklist

- [ ] Both `baseline` and `experimental` variants render without route-state regression.
- [ ] Secondary tabs (`Monitors`, `Activity`, `Templates`) are reachable through `More views` in reduced IA.
- [ ] Deep-link/tab restoration preserves active tab visibility when selected tab is not primary.

### Terminology consistency checklist

- [ ] Tab labels use canonical terms (`Feeds`, `Monitors`, `Activity`, `Articles`, `Reports`).
- [ ] Quick actions and task-view hints match canonical terms.
- [ ] Context docs link label matches active tab guidance label (`Learn more: <label>`).
- [ ] Help docs routes resolve per tab mapping in `WATCHLISTS_TAB_HELP_DOCS`.

## Adoption Metrics: Baseline and Post-Change Comparison

### Baseline snapshot (from Stage 1 telemetry export)

Source: `Docs/Plans/watchlists_ux_stage1_telemetry_export_2026_02_23.md`

| Metric | Baseline (2026-02-23) |
|---|---:|
| UC1-F1 First source setup | 92.96% (66/71) |
| UC1-F2 Time-to-first-review median | 567.49s (0.16h), n=1 |
| UC1-F3 Triage completion (>=20/day) | 0.00% (0/2) |
| UC2-F1 Pipeline completion | 56.72% (38/67) |
| UC2-F2 Text output success | 0.06% (2/3182 completed runs) |
| UC2-F3 Audio output success | 0.03% (1/3182 completed runs) |

### IA experiment adoption comparison

Use `GET /api/v1/watchlists/telemetry/ia-experiment/summary` and compare `baseline` vs `experimental` variants on:

- `avg_transitions`
- `avg_visited_tabs`
- `reached_target_sessions / sessions`
- `avg_session_seconds`

Decision thresholds are defined in:
- `Docs/Product/Watchlists_IA_Reduced_Navigation_Rollout_Gates_2026_02_24.md`

## Validation Commands

```bash
cd apps/packages/ui
bunx vitest run \
  src/components/Option/Watchlists/__tests__/watchlists-terminology-contract.test.ts \
  src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.experimental-ia.test.tsx \
  src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.help-links.test.tsx \
  src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.orientation-guidance.test.tsx \
  src/routes/__tests__/option-watchlists.route-state.test.tsx
```
