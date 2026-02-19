# Implementation Plan: HCI Review - Dashboard & At-a-Glance Overview

## Scope

Pages: `app/page.tsx`, `components/dashboard/*`
Finding IDs: `1.1` through `1.10`

## Finding Coverage

- `1.1` (Critical): No request latency metrics (p50/p95/p99) on dashboard
- `1.2` (Critical): No error rate or failure rate indicator
- `1.3` (Critical): No LLM token consumption or cost burn rate
- `1.4` (Important): Activity chart limited to 7-day fixed window
- `1.5` (Important): System Health Grid uses heuristic, not live health checks
- `1.6` (Important): RecentActivityCard shows only 5 audit entries with minimal context
- `1.7` (Important): AlertsBanner is a single-line yellow bar with no severity breakdown
- `1.8` (Nice-to-Have): No uptime or "time since last incident" indicator
- `1.9` (Nice-to-Have): No cache hit rate or RAG performance metrics
- `1.10` (Important): No queue depth or background job status

## Key Files

- `admin-ui/app/page.tsx` -- Main dashboard, fetches 11 concurrent API calls
- `admin-ui/components/dashboard/StatsGrid.tsx` -- 4-card metric grid (users, orgs, providers, storage)
- `admin-ui/components/dashboard/ActivitySection.tsx` -- Area chart (7-day) + 3-item health grid
- `admin-ui/components/dashboard/RecentActivityCard.tsx` -- Last 5 audit entries
- `admin-ui/components/dashboard/AlertsBanner.tsx` -- Yellow bar with alert count
- `admin-ui/components/dashboard/DashboardHeader.tsx` -- Title + server status pill
- `admin-ui/components/dashboard/QuickActionsCard.tsx` -- 6-item navigation grid
- `admin-ui/lib/api-client.ts` -- All API call definitions

## Stage 1: Operational KPI Cards

**Goal**: Surface latency, error rate, and cost burn rate on the dashboard so admins can assess platform health without navigating away.
**Success Criteria**:
- StatsGrid expands from 4 to 6-8 cards (responsive grid adjusts).
- New cards include: request latency (p95), error rate (%), daily cost ($), and active jobs/queue depth.
- Each card shows current value + trend indicator (up/down arrow vs. previous period).
- Data sourced from existing endpoints (`/admin/usage/daily`, `/admin/llm-usage/summary`, `/jobs/stats`, `/monitoring/metrics`).
- Graceful fallback if any endpoint is unavailable (shows "N/A" not broken card).
**Tests**:
- Unit tests for StatsGrid rendering with 6-8 cards.
- Tests for fallback when individual metric endpoints fail.
- Snapshot test for responsive grid at 3 breakpoints.
**Status**: Complete

## Stage 2: Real Health Checks + Alert Severity Breakdown

**Goal**: Replace heuristic health indicators with actual health endpoint data and make alerts actionable on the dashboard.
**Success Criteria**:
- ActivitySection health grid calls `/health`, `/llm/health`, `/rag/health` directly instead of inferring from loaded data.
- Health grid expanded to cover all subsystems: API, Database, LLM, RAG, TTS, STT, Embeddings, Cache.
- Each subsystem shows real status (healthy/degraded/down) with last-checked timestamp.
- AlertsBanner shows severity breakdown: X critical, Y warning, Z info (color-coded).
- Critical alerts render in red, not yellow.
**Tests**:
- Unit tests for health status normalization from each endpoint.
- Tests for AlertsBanner rendering with mixed severity counts.
- Tests for health grid rendering when individual health endpoints fail.
**Status**: Complete

## Stage 3: Activity Chart Time Range + Enhanced Recent Activity

**Goal**: Give admins control over the activity chart time window and make recent activity entries more useful.
**Success Criteria**:
- Activity chart has time range selector: 24h, 7d, 30d.
- Selecting a range re-fetches data at appropriate granularity (hourly for 24h, daily for 7d/30d).
- RecentActivityCard shows 10 entries (up from 5) with severity icon, resource type badge, and user name (not just ID).
- Entries expandable to show full details inline.
**Tests**:
- Unit tests for time range selector state management.
- Tests for chart data transformation at different granularities.
- Tests for RecentActivityCard rendering with expanded detail.
**Status**: Complete

## Stage 4: Queue Depth, Uptime, and Cache Metrics

**Goal**: Add secondary operational indicators that round out the admin's system awareness.
**Success Criteria**:
- Dashboard includes job queue summary card: active/queued/failed counts sourced from `/jobs/stats`.
- DashboardHeader or a new card shows uptime % and "last incident" timestamp sourced from `/incidents`.
- Health grid includes RAG cache hit rate sourced from `/rag/health` or `/metrics/text`.
- All new cards use existing skeleton loader patterns during loading.
**Tests**:
- Unit tests for job queue summary card with various queue states.
- Tests for uptime calculation from incident history.
- Tests for cache metric parsing from Prometheus text format.
**Status**: Complete

## Dependencies

- Backend endpoints must expose latency percentiles via `/admin/stats` or `/metrics/text`.
- If latency metrics aren't available from the backend, Stage 1 should add a TODO and show "N/A" with a tooltip explaining the requirement.
- No new backend endpoints should be needed for Stages 2-4 (all data sources already exist).
