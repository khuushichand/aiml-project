# Router Analytics Usage View Design

**Date:** 2026-03-01
**Status:** Approved
**Owner:** Admin UI / Usage Analytics

## 1. Objective

Replace the current `/usage` experience with a TokenRouter-style operations surface that:

- Uses a thin frontend over backend aggregate APIs.
- Delivers full tab set in steps: `Status`, `Quota`, `Providers`, `Access`, `Network`, `Models`, `Conversations`, `Log`.
- Stays aligned with the existing `admin-ui` design system and navigation patterns.

## 2. Decision Summary

- **Route strategy:** Keep `/usage`; redesign in place.
- **Architecture:** New backend `router-analytics` aggregate API; frontend primarily renders returned data.
- **Parity target:** Full parity with screenshot concepts, including `Remote IP`, `User Agent`, and token-name breakdowns.
- **Rollout sequence:** Step 1 `Status`; then add one tab per step in screenshot order.
- **Visual language:** Adapt to existing `admin-ui` tokens/components (no standalone cloned theme system).

## 3. High-Level Architecture

### 3.1 Backend

Add a new endpoint namespace under:

- `/api/v1/admin/router-analytics/...`

These endpoints return pre-aggregated payloads by tab and time window. The goal is to minimize frontend data shaping and keep UI logic simple.

### 3.2 Frontend

`/usage` becomes a thin rendering shell:

- Tab container and URL-state routing.
- Shared time/filter controls.
- Per-tab presentational components with lightweight data hooks.

The frontend should avoid recomputing heavy groupings and should trust backend aggregate payloads.

## 4. Rollout Plan (Tab-by-Tab)

1. Step 1: `Status`
2. Step 2: `Quota`
3. Step 3: `Providers`
4. Step 4: `Access`
5. Step 5: `Network`
6. Step 6: `Models`
7. Step 7: `Conversations`
8. Step 8: `Log`

Tabs may be visible before delivery with disabled/coming-soon state if needed to preserve information architecture.

## 5. Backend API Contract

### 5.1 Shared Query Model

Common query parameters:

- `range`: `realtime | 1h | 8h | 24h | 7d | 30d`
- `org_id`: optional
- `provider`: optional
- `model`: optional
- `token_id`: optional
- `granularity`: optional (`1m | 5m | 15m | 1h`)

All responses include:

- `generated_at`
- `data_window` (effective start/end)
- Optional freshness metadata (`stale_seconds`, `partial`, `warnings`)

### 5.2 Endpoints

1. `GET /api/v1/admin/router-analytics/status`
- KPI cards + usage series + provider availability summary.

2. `GET /api/v1/admin/router-analytics/status/breakdowns`
- Tabular breakdowns:
  - `providers[]`
  - `models[]`
  - `token_names[]`
  - `remote_ips[]`
  - `user_agents[]`

3. `GET /api/v1/admin/router-analytics/quota`
- Quota utilization, thresholds, exceeded entities.

4. `GET /api/v1/admin/router-analytics/providers`
- Provider routing/health/latency/failover metrics.

5. `GET /api/v1/admin/router-analytics/access`
- Token/key-level usage and access posture.

6. `GET /api/v1/admin/router-analytics/network`
- IP/UA/origin telemetry and related network-level errors/events.

7. `GET /api/v1/admin/router-analytics/models`
- Model-level usage/latency/cost/throughput distribution.

8. `GET /api/v1/admin/router-analytics/conversations`
- Session/conversation aggregates.

9. `GET /api/v1/admin/router-analytics/log`
- Router decision timeline and system-level routing events.

10. `GET /api/v1/admin/router-analytics/meta`
- Filter option catalogs and display metadata.

### 5.3 Relationship to Existing Usage APIs

Existing endpoints (`/admin/usage/*`, `/admin/llm-usage*`) remain available and unchanged. `router-analytics` is additive and purpose-built for dashboard rendering.

## 6. Data Model and Aggregation

### 6.1 `llm_usage_log` Enrichment

Add nullable fields to usage logging:

- `remote_ip`
- `user_agent`
- `token_name`
- Optional: `conversation_id` (recommended for conversation-quality aggregation)

### 6.2 Write-Path Enrichment

On each logged LLM usage event:

- Capture resolved client IP (respecting trusted proxy rules).
- Capture `User-Agent`.
- Resolve token/key display label into `token_name` (fallback to stable ID label).

### 6.3 Aggregate Storage

Introduce aggregate tables for efficient reads, for example:

- `router_usage_timeseries` (bucketed by time/provider/model)
- `router_usage_breakdowns` (dimensioned by provider/model/token/ip/ua)
- `router_events` (routing/failover/rate-limit decision feed)

Aggregation jobs must be:

- Incremental
- Idempotent (upsert by bucket + dimension key)
- Compatible across SQLite/Postgres backends

### 6.4 Realtime Strategy

For `range=realtime`, backend may blend:

- Recent raw data for near-live buckets
- Precomputed aggregates for older buckets in the same requested window

### 6.5 Backward Compatibility

- New columns are nullable with no breaking schema requirement for legacy rows.
- Missing historical values are grouped under `unknown`.

### 6.6 Performance Constraints

- Indexes on critical predicates:
  - `(ts)`
  - `(provider, model, ts)`
  - `(remote_ip, ts)`
  - `(token_name, ts)`
  - `(org_id, ts)` where applicable
- High-cardinality dimensions return `Top N + other`.

## 7. Frontend Composition

### 7.1 `/usage` Page Shell

- Header: page title, range selector, refresh control, optional realtime indicator.
- Tab strip: full eight-tab model.
- URL-driven state:
  - `tab`
  - `range`
  - selected filters (`provider`, `model`, `token_id`)

### 7.2 `Status` Tab Layout

Initial tab includes:

- KPI cards row:
  - Requests
  - Prompt/Generated tokens
  - Avg latency
  - Avg generation tok/s
- Usage chart by model/provider over selected bucket window.
- Provider summary line (`available`, `online`).
- Breakdown tables:
  - Providers
  - Models
  - Token Names
  - Remote IPs
  - User Agents

### 7.3 Frontend Files (Planned)

- `admin-ui/app/usage/page.tsx` (route shell)
- `admin-ui/app/usage/components/RouterUsageHeader.tsx`
- `admin-ui/app/usage/components/RouterUsageTabs.tsx`
- `admin-ui/app/usage/components/status/*`
- `admin-ui/lib/router-analytics-client.ts`
- `admin-ui/lib/router-analytics-types.ts`

## 8. Error Handling and Resilience

### 8.1 Backend

- Strict validation for range/granularity/grouping.
- Structured partial-response support:
  - `partial: true`
  - `warnings[]` with machine-readable reason keys.

### 8.2 Frontend

- Per-tab failures are isolated.
- Each tab supports retry without full-page reset.
- Distinguish:
  - no data
  - stale data
  - failed query

## 9. Testing Strategy

### 9.1 Backend Tests

- Unit tests:
  - Aggregation math
  - Bucketing logic
  - Top-N plus `other`
  - Parameter validation
- Integration tests:
  - Endpoint responses with seeded usage data
  - Mixed legacy/new rows (`NULL` enriched fields)

### 9.2 Frontend Tests

- URL-tab routing behavior.
- `Status` rendering from mock payloads (cards/chart/tables).
- Realtime polling lifecycle and manual refresh flows.
- Responsive and accessibility checks in current test style.

### 9.3 Performance Verification

- Measure endpoint latency at realistic cardinalities.
- Confirm query/index plans on supported backends.

## 10. Risks and Mitigations

1. High-cardinality dimensions (`user_agent`, `remote_ip`)
- Mitigation: aggregate-first model, row caps, `other` bucket, index strategy.

2. Freshness ambiguity in operational views
- Mitigation: explicit freshness metadata and UI labeling.

3. Historical gaps for newly added fields
- Mitigation: `unknown` grouping + progressive enrichment.

4. Scope expansion across 8 tabs
- Mitigation: strict one-tab-per-step rollout sequence.

## 11. Acceptance Criteria

- `/usage` renders new tab shell and loads tab data from `router-analytics` endpoints.
- `Status` tab reproduces target information model (KPI + chart + breakdown tables).
- `Remote IP`, `User Agent`, and token-name breakdowns are available via backend aggregates.
- Existing usage endpoints remain functional and unchanged.
- Tab rollout can proceed incrementally without architecture changes.

