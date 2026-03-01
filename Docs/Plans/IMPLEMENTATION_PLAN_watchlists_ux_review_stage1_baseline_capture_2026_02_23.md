# Watchlists UX Review Stage 1 Baseline Capture (2026-02-23)

**Goal:** Start Stage 1 execution by recording ownership, baseline funnel definitions, dependency order, and initial verification evidence.

**Status:** Complete

## 1) Owner and Reviewer Assignments

| Group | Owner (Assignee) | Reviewer (Assignee) |
|---|---|---|
| 01 | Robert | Mike |
| 02 | Mike | Robert |
| 03 | Robert | Mike |
| 04 | Mike | Robert |
| 05 | Robert | Mike |
| 06 | Mike | Robert |
| 07 | Robert | Mike |
| 08 | Mike | Robert |
| 09 | Robert | Mike |
| 10 | Mike | Robert |

## 2) Baseline Funnel Metrics (UC1 and UC2)

| Funnel | Metric | Definition | Baseline (2026-02-23) | Source |
|---|---|---|---|---|
| UC1 | UC1-F1 First source setup | Percent of new users adding at least one source in first session | 92.96% (66/71 users) | `Docs/Plans/watchlists_ux_stage1_telemetry_export_2026_02_23.md` |
| UC1 | UC1-F2 Time-to-first-review | Median time from first source creation to first item marked reviewed/read | 0.16 hours median (567.49s, n=1) | `Docs/Plans/watchlists_ux_stage1_telemetry_export_2026_02_23.md` |
| UC1 | UC1-F3 Triage completion | Percent of active users reviewing at least 20 items/day | 0.00% (0/2 users) | `Docs/Plans/watchlists_ux_stage1_telemetry_export_2026_02_23.md` |
| UC2 | UC2-F1 Pipeline completion | Percent of users who complete source -> monitor -> first run setup | 56.72% (38/67 users) | `Docs/Plans/watchlists_ux_stage1_telemetry_export_2026_02_23.md` |
| UC2 | UC2-F2 Text output success | Percent of completed runs with report output generated | 0.06% (2/3182 completed runs) | `Docs/Plans/watchlists_ux_stage1_telemetry_export_2026_02_23.md` |
| UC2 | UC2-F3 Audio output success | Percent of completed runs with audio asset generated | 0.03% (1/3182 completed runs) | `Docs/Plans/watchlists_ux_stage1_telemetry_export_2026_02_23.md` |

Notes:
- Baseline metrics were computed from local telemetry exports generated from `Databases/**/Media_DB_v2.db` snapshots.
- Export summary artifact: `Docs/Plans/watchlists_ux_stage1_telemetry_export_2026_02_23.md`.
- Aggregation assumptions and formulas are recorded in the summary export file.

## 3) Dependency and Phase Order Approval

Approved execution order for remediation:
1. Phase 2: Groups 01, 02, 03
2. Phase 3: Groups 04, 05, 07, 08
3. Phase 4: Groups 06, 09, 10
4. Phase 5: Program closeout and release gates

Dependency source: `Docs/Plans/IMPLEMENTATION_PLAN_watchlists_ux_review_program_coordination_index_2026_02_23.md`

## 4) Baseline Verification Evidence (Captured)

| Scope | Command | Result | Evidence |
|---|---|---|---|
| Help and docs links | `bun run test:watchlists:help` | Passed (2 files, 7 tests) | `/tmp/watchlists_ux_stage1_baseline_watchlists_help_2026_02_23.txt` |
| IA, terminology, route state | `bunx vitest run src/components/Option/Watchlists/__tests__/watchlists-terminology-contract.test.ts src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.experimental-ia.test.tsx src/routes/__tests__/option-watchlists.route-state.test.tsx --maxWorkers=1 --no-file-parallelism` | Passed (3 files, 10 tests) | `/tmp/watchlists_ux_stage1_baseline_ia_terms_routes_2026_02_23.txt` |
| Telemetry contract | `bunx vitest run src/utils/__tests__/watchlists-onboarding-telemetry.test.ts src/utils/__tests__/watchlists-ia-experiment-telemetry.test.ts --maxWorkers=1 --no-file-parallelism` | Passed (2 files, 4 tests) | `/tmp/watchlists_ux_stage1_baseline_telemetry_contracts_2026_02_23.txt` |
| Group plan status initialization | `cd Docs/Plans && rg -n '^## Stage [0-9]+:|^\*\*Status\*\*:' IMPLEMENTATION_PLAN_watchlists_ux_review_0*_2026_02_23.md` | Captured stage/status map for all group plans | `/tmp/watchlists_ux_stage1_plan_status_matrix_2026_02_23.txt` |

## 5) Remaining Stage 1 Completion Tasks

- None. Stage 1 completion criteria are satisfied for owner/reviewer assignment and UC1/UC2 baseline capture from telemetry exports.
