# Implementation Plan: HCI Review - Information Architecture Gaps

## Scope

New pages and cross-page data surfaces
Finding IDs: `9.1` through `9.9`

## Finding Coverage

- `9.1` (Critical): No system configuration overview page
- `9.2` (Critical): No dependency health dashboard (external service status)
- `9.3` (Important): No API endpoint usage heatmap
- `9.4` (Important): No storage usage breakdown per user or media type
- `9.5` (Important): No webhook/integration management
- `9.6` (Important): No user onboarding/invitation flow visibility
- `9.7` (Important): No rate limit monitoring (who's hitting limits, how often)
- `9.8` (Nice-to-Have): No background task queue visualization
- `9.9` (Nice-to-Have): No email/notification delivery status tracking

## Key Files

- `admin-ui/lib/navigation.ts` -- Route definitions (needs new routes)
- `admin-ui/app/monitoring/page.tsx` -- Existing monitoring (health grid, notifications)
- `admin-ui/app/usage/page.tsx` -- Existing usage analytics
- `admin-ui/app/page.tsx` -- Dashboard (storage display in StatsGrid)
- `admin-ui/lib/api-client.ts` -- API methods

## Stage 1: System Configuration Overview Page

**Goal**: Give admins a single page showing the full platform configuration state.
**Success Criteria**:
- New page at `app/config/page.tsx` (route `/config`).
- Added to navigation under "Advanced" section.
- Page sections:
  - **Authentication**: Current auth mode (single_user/multi_user), session settings, MFA policy.
  - **Storage**: Database backend, storage path, total/used capacity.
  - **Features**: Enabled/disabled feature flags summary (from `/admin/feature-flags`).
  - **Providers**: Configured LLM providers with status (from `/llm/providers`).
  - **Services**: Enabled subsystems (RAG, TTS, STT, MCP, etc.) with basic config.
  - **Server**: Version, uptime, Python version, OS, deployment mode.
- All sections read-only with links to relevant management pages.
- Data sourced from existing endpoints: `/health`, `/llm/providers`, `/admin/feature-flags`, `/admin/stats`.
**Tests**:
- Unit test for config page rendering with full data.
- Unit test for each section with missing/unavailable data.
- Navigation test: config page accessible from sidebar.
**Status**: Complete

## Stage 2: External Dependency Health Dashboard

**Goal**: Show the availability and performance of all external services the platform depends on.
**Success Criteria**:
- New section on monitoring page or standalone page at `app/dependencies/page.tsx`.
- Lists all configured external providers with health indicators:
  - LLM providers: OpenAI, Anthropic, Cohere, etc. (from `/llm/providers`).
  - Each shows: status (reachable/unreachable), last checked, response time (ms), error rate (24h).
- Health check runs on page load with "Refresh All" button.
- Individual "Test" button per provider (reuses existing test connectivity logic from providers page).
- Unreachable providers highlighted in red with time since last successful response.
- Historical availability chart per provider (if Prometheus metrics available).
**Tests**:
- Unit test for dependency health grid rendering.
- Unit test for test connectivity button and result display.
- Unit test for unreachable provider highlighting.
**Status**: Complete

## Stage 3: API Endpoint Usage + Storage Breakdown + Rate Limit Monitoring

**Goal**: Fill the three most impactful information gaps for operational understanding.
**Success Criteria**:
- Usage page adds "Endpoints" tab showing per-endpoint metrics: path, method, request count (24h), avg latency, error rate, p95 latency.
- Endpoint table sortable by any column; filterable by method (GET/POST/PUT/DELETE).
- Data sourced from `/admin/usage/daily` or `/metrics/text` Prometheus endpoint metrics.
- Storage page or section (in usage or data-ops): breakdown by user (top 10 consumers), by media type (video, audio, documents, embeddings).
- Storage breakdown shows bar chart or treemap visualization.
- Rate limit monitoring: new section on resource-governor page or usage page.
- Shows: user/role, policy name, rejection count (24h/7d), last rejection timestamp.
- Top-throttled users/roles highlighted.
**Tests**:
- Unit test for endpoint usage table rendering and sorting.
- Unit test for storage breakdown chart with user/media type data.
- Unit test for rate limit events table.
**Status**: Complete

## Stage 4: Onboarding Visibility + Queue Visualization + Notification Tracking

**Goal**: Complete the remaining Nice-to-Have information surfaces.
**Success Criteria**:
- New "Invitations" section on users page or standalone page: lists all pending invitations with status (sent, accepted, expired), email, invited by, role, org, sent date, expiry date.
- Invitation funnel metrics: total sent, total accepted, conversion rate.
- Jobs page adds "Queue Depth" chart: time-series of queue depth (queued + processing) over last 24h.
- Queue throughput metrics: jobs completed/hour, average processing time.
- Monitoring page notifications section adds delivery dashboard: total sent, delivery rate, failure rate, by channel (email, slack, webhook, discord).
- Failed notifications show error details and retry button.
**Tests**:
- Unit test for invitation list rendering with mixed statuses.
- Unit test for funnel metrics calculation.
- Unit test for queue depth chart rendering.
- Unit test for notification delivery dashboard.
**Status**: Complete

## Dependencies

- Stage 1 is primarily frontend; uses existing endpoints. Server version/uptime may need a new backend field in `/health` response.
- Stage 2 dependency health checks reuse existing provider test connectivity. Historical data requires Prometheus metrics.
- Stage 3 endpoint usage requires either Prometheus `http_request_duration_seconds` metrics or a new backend endpoint aggregating request logs.
- Stage 3 storage breakdown by user/media type may require new backend endpoint `GET /admin/storage/breakdown`.
- Stage 4 invitation tracking can aggregate existing `GET /orgs/{org_id}/invites` results when `GET /admin/invitations` is unavailable.
- Stage 4 queue depth history requires either Prometheus `job_queue_depth` metric or a new backend endpoint.
