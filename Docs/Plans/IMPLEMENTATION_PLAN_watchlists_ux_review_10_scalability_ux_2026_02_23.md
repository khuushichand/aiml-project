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

## Stage 3: Bulk Action and Background Operation Model
**Goal**: Ensure large operations are transparent, recoverable, and non-blocking.
**Success Criteria**:
- Long-running batch actions provide progress and completion/failure summaries.
- Bulk operations avoid locking core interaction surfaces.
- Recovery actions are available for partial failures at scale.
**Tests**:
- Add tests for batch operation progress states and terminal outcomes.
- Add tests for partial failure reconciliation and retry paths.
**Status**: Not Started

## Stage 4: Polling, Notifications, and Refresh Efficiency
**Goal**: Reduce redundant background activity while preserving freshness.
**Success Criteria**:
- Polling intervals and payload sizes adapt to workload and active states.
- Notification polling avoids duplicate work and unnecessary user noise.
- Refresh actions are cheap and predictable across tabs.
**Tests**:
- Add tests for polling start/stop conditions and deduplication behavior.
- Add tests for notification grouping under high event volumes.
**Status**: Not Started

## Stage 5: Scale Readiness Validation and Runbook
**Goal**: Certify Watchlists UX readiness for larger analyst deployments.
**Success Criteria**:
- QA runbook includes scale scenarios (5, 50, 200 feeds; high item counts).
- Known scale constraints and mitigations are documented.
- Release gate requires passing scale smoke checks on core surfaces.
**Tests**:
- Run scale scenario suite and record timings/evidence.
- Validate that core UC1/UC2 workflows remain functional under load.
**Status**: Not Started

## Execution Notes

### 2026-02-24 - Stage 1 completion (scale profiles + baseline harness)

- Added explicit scale profile and per-surface performance budget contracts:
  - `apps/packages/ui/src/components/Option/Watchlists/shared/scale-profiles.ts`
- Added a benchmark harness covering render/mutation preparation paths for feeds, monitors, activity, and articles:
  - `apps/packages/ui/src/components/Option/Watchlists/shared/scale-benchmark.ts`
- Added scale benchmark regression coverage and execution script:
  - `apps/packages/ui/src/components/Option/Watchlists/shared/__tests__/scale-benchmark.test.ts`
  - `apps/packages/ui/package.json` (`test:watchlists:scale`)
- Published Stage 1 baseline timing artifact with documented bottlenecks and constraints:
  - `Docs/Plans/WATCHLISTS_SCALE_BASELINE_BUDGETS_2026_02_24.md`
- Stage 1 validation evidence:
  - `cd apps/packages/ui && bun run test:watchlists:scale`

### 2026-02-24 - Stage 2 completion (high-volume list + reader optimization)

- Added high-volume client filtering helper for Activity (runs) to avoid a 200-row hard cliff when both monitor and status filters are active:
  - `apps/packages/ui/src/components/Option/Watchlists/RunsTab/runs-filter-fetch.ts`
  - `apps/packages/ui/src/components/Option/Watchlists/RunsTab/RunsTab.tsx`
- Added OPML group URL cache (TTL-based) in Feeds filtering path to reduce repeated OPML export overfetch on repeated refreshes:
  - `apps/packages/ui/src/components/Option/Watchlists/SourcesTab/SourcesTab.tsx`
- Added Items reader smart-count cache (TTL-based) with mutation-triggered invalidation to reduce repeated 5-request fan-out on unchanged filter state:
  - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/ItemsTab.tsx`
- Added Stage 2 regression/performance coverage:
  - `apps/packages/ui/src/components/Option/Watchlists/RunsTab/__tests__/runs-filter-fetch.test.ts`
  - `apps/packages/ui/src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.advanced-filters.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.advanced-details.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.scale-responsive.test.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/__tests__/items-utils.performance.test.ts`
  - `apps/packages/ui/package.json` (`test:watchlists:scale`)
- Stage 2 validation evidence:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.scale-responsive.test.tsx src/components/Option/Watchlists/ItemsTab/__tests__/ItemsTab.keyboard-shortcuts.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/RunsTab.advanced-filters.test.tsx src/components/Option/Watchlists/RunsTab/__tests__/runs-filter-fetch.test.ts src/components/Option/Watchlists/SourcesTab/__tests__/SourcesTab.advanced-details.test.tsx src/components/Option/Watchlists/shared/__tests__/scale-benchmark.test.ts src/components/Option/Watchlists/ItemsTab/__tests__/items-utils.performance.test.ts --maxWorkers=1 --no-file-parallelism`
  - `cd apps/packages/ui && bun run test:watchlists:scale`
