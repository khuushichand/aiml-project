# Watchlists UX Review Group 10 - Scalability of UX Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Keep Watchlists usable and responsive as users scale from small setups to high-volume source and item workloads.

**Architecture:** Apply scalable interaction patterns (virtualization, background bulk operations, adaptive polling, and dataset-aware defaults) across Watchlists list and reader surfaces while maintaining feature parity.

**Tech Stack:** React, TypeScript, Watchlists service pagination APIs, Ant Design table/list/pagination, client-side performance profiling tools, Vitest + performance-oriented regression tests.

---

## Scope

- UX dimensions covered: behavior and usability at 5, 50, and 200+ feeds/monitors/items.
- Primary surfaces:
  - `apps/packages/ui/src/components/Option/Watchlists/SourcesTab/SourcesTab.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/JobsTab/JobsTab.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/ItemsTab.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/RunsTab/RunsTab.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/WatchlistsPlaygroundPage.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/items-utils.ts`
- Key outcomes:
  - No major usability cliffs as data volume grows.
  - Bulk actions remain observable and safe at scale.
  - Polling and refresh behaviors remain efficient.

## Stage 1: Scale Profiles and Performance Budget Definition
**Goal**: Define expected load profiles and acceptable UX performance thresholds.
**Success Criteria**:
- Benchmarked profiles are defined for feeds, monitors, runs, and item volumes.
- Per-surface performance budget exists (render latency, interaction latency, refresh cadence).
- Priority bottlenecks and architectural constraints are documented.
**Tests**:
- Add benchmark harness for representative data volumes in key Watchlists views.
- Capture baseline timings for render and mutation flows.
**Status**: Complete

### Stage 1 Execution Notes (2026-02-23)

- Added benchmark harness covering scale-sensitive Watchlists pipelines:
  - `apps/packages/ui/src/components/Option/Watchlists/__tests__/watchlists-scale-baseline.bench.test.ts`
- Captured baseline timings for:
  - Sources filter/ordering pipeline (`5/50/200` feeds)
  - Items sort pipeline (`100/1,000/5,000` items)
  - Run notification dedupe/grouping burst (`1,000` events)
- Published scale profile + budget registry and constraint inventory:
  - `Docs/Plans/WATCHLISTS_SCALE_PROFILE_BASELINE_2026_02_23.md`

### Stage 1 Validation Evidence

- `bunx vitest run src/components/Option/Watchlists/__tests__/watchlists-scale-baseline.bench.test.ts`

## Stage 2: High-Volume List and Reader Optimization
**Goal**: Improve rendering and interaction efficiency for large datasets.
**Success Criteria**:
- Lists/tables use scalable rendering strategies where needed.
- Source sidebar and items list loading avoids hard cliffs and unnecessary overfetch.
- Reader interactions stay responsive under high-volume filters.
**Tests**:
- Add tests for pagination/scroll behavior under large mocked datasets.
- Add performance regression checks for items selection and filter changes.
**Status**: Complete

### Stage 2 Execution Notes (2026-02-23)

- Added incremental source-sidebar rendering for large feed catalogs in `ItemsTab`:
  - Source list now renders an initial bounded window and expands on scroll instead of eagerly rendering all rows.
  - Added explicit source-window guidance copy (`showing X of Y`) for progressive list expansion visibility.
- Added source-catalog cap signaling for hard limits:
  - When source volume exceeds the reader load cap (`1000`), Items now shows an explicit cap hint instead of silently truncating.
- Added scale helper utilities in `items-utils` for deterministic render-window growth and scroll-threshold expansion decisions:
  - `getInitialSourceRenderCount`
  - `getNextSourceRenderCount`
  - `shouldExpandSourceRenderWindow`
- Added high-volume list/reader regression coverage:
  - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.scale-behavior.test.tsx`
  - Covers incremental source rendering, scroll-triggered expansion, cap hint visibility, search debounce, and selection non-refetch behavior.
- Extended scale benchmark coverage for selection/filter responsiveness:
  - `apps/packages/ui/src/components/Option/Watchlists/__tests__/watchlists-scale-baseline.bench.test.ts`
  - Added `selection_filter_ms` budget check for rapid selection/query pipeline loops.

### Stage 2 Validation Evidence

- `bunx vitest run src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.scale-behavior.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.batch-controls.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/items-utils.test.ts src/components/Option/Watchlists/__tests__/watchlists-scale-baseline.bench.test.ts`
- `/tmp/bandit_watchlists_group10_stage2_frontend_scope_2026_02_23.json`

## Stage 3: Bulk Action and Background Operation Model
**Goal**: Ensure large operations are transparent, recoverable, and non-blocking.
**Success Criteria**:
- Long-running batch actions provide progress and completion/failure summaries.
- Bulk operations avoid locking core interaction surfaces.
- Recovery actions are available for partial failures at scale.
**Tests**:
- Add tests for batch operation progress states and terminal outcomes.
- Add tests for partial failure reconciliation and retry paths.
**Status**: Complete

### Stage 3 Execution Notes (2026-02-23)

- Added persistent batch-progress state to Articles bulk review actions:
  - Tracks scope, total, processed, success/failure counts, failed IDs, and running/completed status.
  - Updates after each 20-item processing chunk to surface long-running operation progress.
- Added in-context batch progress UI in `ItemsTab`:
  - Progress panel with processed/total counts and progress bar status (`active`, `success`, `exception`).
  - Running summary text and terminal completion summary (`Completed X of Y. Z failed.`).
- Added explicit partial-failure recovery action:
  - New `Retry failed` action replays only failed IDs from the previous batch attempt without blocking the rest of the reader surface.
  - Existing selection reconciliation behavior remains intact (successful IDs are removed from selection; failed IDs remain recoverable).
- Added regression coverage for background-operation transparency and recovery:
  - Extended `ItemsTab.batch-controls` tests for:
    - in-progress batch status visibility during high-volume operations
    - partial-failure retry path with post-retry reconciliation

### Stage 3 Validation Evidence

- `bunx vitest run src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.batch-controls.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.scale-behavior.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/items-utils.test.ts src/components/Option/Watchlists/__tests__/watchlists-scale-baseline.bench.test.ts`
- `bun run test:watchlists:a11y`
- `/tmp/bandit_watchlists_group10_stage3_frontend_scope_2026_02_23.json`

## Stage 4: Polling, Notifications, and Refresh Efficiency
**Goal**: Reduce redundant background activity while preserving freshness.
**Success Criteria**:
- Polling intervals and payload sizes adapt to workload and active states.
- Notification polling avoids duplicate work and unnecessary user noise.
- Refresh actions are cheap and predictable across tabs.
**Tests**:
- Add tests for polling start/stop conditions and deduplication behavior.
- Add tests for notification grouping under high event volumes.
**Status**: Complete

### Stage 4 Execution Notes (2026-02-23)

- Added shared Watchlists polling decision utilities:
  - `hasActiveWatchlistRuns`
  - `resolveAdaptiveRunNotificationsPollMs`
  - `resolveRunNotificationsPageSize`
  - Implemented in `apps/packages/ui/src/components/Option/Watchlists/RunsTab/polling-utils.ts`.
- Hardened shell-level run notification polling in `WatchlistsPlaygroundPage`:
  - Added in-flight request guard to prevent overlapping polling requests.
  - Added visibility-aware adaptive poll intervals (active vs idle vs background tab).
  - Added adaptive notification payload sizing (smaller when idle/hidden).
  - Added visibility-change listener to update polling cadence predictably.
- Updated `RunsTab` active-run detection to use shared status utility, including queued/pending/running consistency for polling start/stop decisions.
- Added Stage 4 regression coverage:
  - `apps/packages/ui/src/components/Option/Watchlists/RunsTab/__tests__/polling-utils.test.ts`
  - Extended `apps/packages/ui/src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.run-notifications.test.tsx` with no-overlap polling coverage.

### Stage 4 Validation Evidence

- `bunx vitest run src/components/Option/Watchlists/RunsTab/__tests__/polling-utils.test.ts src/components/Option/Watchlists/RunsTab/__tests__/run-notifications.test.ts src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.advanced-filters.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.accessibility-live-region.test.tsx src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.run-notifications.test.tsx src/components/Option/Watchlists/__tests__/WatchlistsPlaygroundPage.help-links.test.tsx`
- `bun run test:watchlists:a11y`
- `/tmp/bandit_watchlists_group10_stage4_frontend_scope_2026_02_23.json`

## Stage 5: Scale Readiness Validation and Runbook
**Goal**: Certify Watchlists UX readiness for larger analyst deployments.
**Success Criteria**:
- QA runbook includes scale scenarios (5, 50, 200 feeds; high item counts).
- Known scale constraints and mitigations are documented.
- Release gate requires passing scale smoke checks on core surfaces.
**Tests**:
- Run scale scenario suite and record timings/evidence.
- Validate that core UC1/UC2 workflows remain functional under load.
**Status**: Complete

### Stage 5 Execution Notes (2026-02-23)

- Added a dedicated scale-readiness runbook artifact with:
  - 5/50/200 profile scenario matrix spanning UC1 and UC2 surfaces
  - known constraints + mitigations for high-volume interactions
  - post-release thresholds and evidence capture protocol
  - `Docs/Plans/WATCHLISTS_SCALE_READINESS_RUNBOOK_2026_02_23.md`
- Added a scripted scale regression release gate for Watchlists:
  - `apps/packages/ui/package.json` (`test:watchlists:scale`)
  - Gate covers benchmark baseline, high-volume Items flows, Sources bulk operations, Jobs/Runs/Outputs density filters, and shell notification behavior.
- Updated baseline scale profile notes to reflect Stage 4 adaptive polling completion and to link the operational runbook:
  - `Docs/Plans/WATCHLISTS_SCALE_PROFILE_BASELINE_2026_02_23.md`

### Stage 5 Validation Evidence

- `bun run test:watchlists:scale`
- `Docs/Plans/WATCHLISTS_SCALE_READINESS_RUNBOOK_2026_02_23.md`
- `/tmp/bandit_watchlists_group10_stage5_frontend_scope_2026_02_23.json`
