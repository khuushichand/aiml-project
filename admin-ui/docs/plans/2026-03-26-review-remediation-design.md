# Admin UI Review Remediation — Staged Plan

**Date:** 2026-03-26
**Scope:** Address all 120 findings from REVIEW.md
**Organization:** By feature area, with a Stage 0 for critical/safety items
**Team:** Solo developer, ~1-2 weeks per stage
**Backend:** Included — both API and UI changes planned together
**Total estimated duration:** ~14-16 weeks

---

## Stage 0: Critical Safety Fixes & Quick Wins (~1.5 weeks)

> Addresses 3 Critical findings, 1 Important safety gap (tiered), and 5 quick wins. Includes backend work for ACP findings.

### Critical Fix 1: ACP Agent Usage Metrics (4.4)

**Problem:** Agent table has zero runtime metrics — admins cannot detect misbehavior or assess ROI.

**Backend (FastAPI):**
- Add `GET /admin/acp/agents/usage` endpoint that aggregates from ACP sessions table:
  - Per-agent: `invocation_count`, `total_tokens`, `total_cost_usd`, `error_count`, `avg_tokens_per_session`
  - Accept `?range=7d|30d` query param
- SQL: `SELECT agent_type, COUNT(*), SUM(total_tokens), ... FROM acp_sessions GROUP BY agent_type`
- No schema migration needed — reads from existing sessions data

**Frontend (`app/acp-agents/page.tsx`):**
- Add columns after "Tools": Invocations, Tokens, Cost, Error Rate (lines 328-335)
- Add `AgentConfig` interface field: `usage?: { invocations: number; total_tokens: number; cost_usd: number; error_rate: number }`
- Fetch usage data on mount via new API endpoint; merge into agent configs by `type`
- Conditionally render "No usage data" if endpoint returns empty

### Critical Fix 2: ACP Session Token Budgets (4.6)

**Problem:** Runaway agents can consume unlimited tokens with no safeguard.

**Backend (FastAPI):**
- Add `max_token_budget` nullable integer field to ACP agent config model (schema migration)
- Add `PATCH /admin/acp/agents/{id}` to update config including budget
- Add middleware in ACP session handler: before each LLM call, check `session.usage.total_tokens + estimated_new_tokens > agent_config.max_token_budget`. If exceeded, set session status to `budget_exceeded` and close
- Add `budget_exceeded` to session status enum

**Frontend:**
- `app/acp-agents/page.tsx`: Add "Token Budget" number input to agent create/edit form (lines 479-539). Default empty (unlimited). Show helper text: "Maximum tokens per session. Leave empty for unlimited."
- `app/acp-sessions/page.tsx`: If session's agent has a budget:
  - Replace plain token count (lines 235-238) with progress bar: `usage.total_tokens / max_token_budget`
  - Color: green <70%, yellow 70-90%, red >90%
  - Add `budget_exceeded` status badge (red) alongside existing status badges

### Critical Fix 3: Plan Deletion Subscriber Check (7.1)

**Problem:** Deleting a plan with active subscribers could break billing.

**Backend (FastAPI):**
- No new endpoint needed — use existing `GET /admin/billing/subscriptions?plan_id={id}&status=active`

**Frontend (`app/plans/page.tsx`, lines 149-167):**
- Before calling `confirm()`, fetch `api.getSubscriptions({ plan_id: plan.id })`
- Filter for non-canceled statuses (`active`, `trialing`, `past_due`, `incomplete`)
- If count > 0: show destructive dialog with "This plan has N active subscriptions. Deleting it will affect those organizations. You must migrate subscribers to another plan first." and **disable the delete button**
- If count === 0: proceed with existing confirm flow

### Safety Fix: PrivilegedActionDialog Tiered Rollout (9.6)

**Problem:** `usePrivilegedActionDialog()` returns `{reason, adminPassword} | null` while `useConfirm()` returns `boolean`. Cannot mechanically swap. 38 files use danger-variant confirms.

**Tiered approach — convert only highest-risk operations:**

**Tier 1 — Require password + reason (5 call sites):**
| Page | Operation | File |
|------|-----------|------|
| Plans | Delete plan | `app/plans/page.tsx` |
| Organizations | Delete org | `app/organizations/page.tsx` |
| BYOK | Delete provider key | `app/byok/page.tsx` |
| Subscriptions | Cancel subscription | `app/subscriptions/page.tsx` |
| Resource Governor | Delete policy | `app/resource-governor/page.tsx` |

Each conversion requires:
1. Import `usePrivilegedActionDialog` instead of (or alongside) `useConfirm`
2. Replace `confirm({...})` with `privilegedAction.prompt({title, message, icon, requirePassword: true})`
3. Check `if (!result) return;` (null = cancelled)
4. Pass `result.reason` and `result.adminPassword` to the API call for audit logging
5. Update the backend delete endpoints to accept optional `reason` and `admin_password` body params

**Tier 2 — Require reason only, no password (leave for later stages):**
Feature flag deletion, backup schedule deletion, incident deletion — addressed in their respective feature-area stages.

**Tier 3 — Keep useConfirm (no change):**
All other danger-variant confirmations (API key revoke, team member removal, alert dismiss, etc.)

### Quick Wins

| ID | Finding | Work Required | Est. Time |
|----|---------|---------------|-----------|
| 3.2 | Key hygiene summary cards not clickable | Wire `onClick` on each of the 4 cards in `api-keys/page.tsx` (lines 292-329) to call `updateFilter()` with relevant params. E.g., "Expiring Soon" sets filter to show keys expiring within 30 days. Add `cursor-pointer hover:border-primary` classes. | 30 min |
| 3.3 | 24h request/error columns permanently N/A | In `UnifiedApiKeysTable.tsx`, check if any row has non-null `requestCount24h`. If none do, skip rendering the `<TableHead>` entries (lines 103-104) and corresponding `<TableCell>` entries (lines 162-163). | 15 min |
| 5.14 | Alert icon-only buttons lack aria-labels | In `AlertsPanel.tsx`, add `aria-label` to 4 buttons: Escalate (line 201), Acknowledge (line 212), Dismiss (line 220), and Show Snoozed toggle (line 98). Mirror existing `title` text. | 15 min |
| 9.5 | Inconsistent loading states (bare "Loading...") | Replace `<div>Loading...</div>` with existing skeleton components across 19 instances in 13 files: `organizations/[id]/page.tsx` (2), `security/page.tsx` (1), `providers/page.tsx` (3), `roles/[id]/page.tsx` (1), `roles/matrix/page.tsx` (1), `users/[id]/api-keys/page.tsx` (1), `teams/[id]/page.tsx` (1), `WatchlistsPanel.tsx` (1), `NotificationsPanel.tsx` (1), `AlertsPanel.tsx` (1), `PermissionGuard.tsx` (1), `MaintenanceSection.tsx` (2), `OrgContextSwitcher.tsx` (1). Use `TableSkeleton`, `CardSkeleton`, or `FormSkeleton` as appropriate. | 2 hrs |
| 9.8 | Export only on 2 of 12+ list pages | Add `<ExportMenu>` to 10 pages: organizations, teams, api-keys, logs, budgets, incidents, jobs, voice-commands, acp-sessions, subscriptions. Each needs: (1) import ExportMenu, (2) add export handler that formats current filtered data as CSV/JSON, (3) place in page header next to existing actions. | 2 hrs |

---

## Stage 1: Dashboard & Overview (~1.5 weeks)

> Addresses findings 1.1–1.14 (minus 1.13 auto-refresh pattern which was a Stage 0 dependency but listed here for completeness).

### Backend Work

| ID | Finding | API Changes |
|----|---------|-------------|
| 1.1 | No active-sessions KPI | Add `active_sessions_count` to `GET /admin/dashboard/stats` response. Query session store for non-expired sessions. |
| 1.2 | No token-consumption KPI | Add `tokens_today` (with `prompt`/`completion` breakdown) and `tokens_trend` to dashboard stats response. Aggregate from LLM usage table. |
| 1.4 | MCP tool invocation rates | Add `mcp_invocations_today` to dashboard stats if MCP metrics are instrumented. Return `null` if not available. |

### Frontend Work

| ID | Finding | UI Changes |
|----|---------|------------|
| 1.1 | No active-sessions KPI | Add 9th card "Active Sessions" to `StatsGrid.tsx` with trend indicator. |
| 1.2 | No token-consumption KPI | Add 10th card "Tokens Today" with prompt/completion sub-text and trend arrow. |
| 1.3 | Cache hit rate buried | Add cache hit rate as secondary metric on the existing RAG subsystem health row, or as an optional 11th StatsGrid card. |
| 1.4 | MCP tool invocation rates | Conditionally render an "MCP Calls" card if backend returns non-null value. |
| 1.5 | Activity chart lacks error/latency overlays | Extend `DashboardActivityChartPoint` with `errors` and `latencyP95Ms`. Add toggleable `<Line>` series to the area chart in `ActivitySection.tsx`. |
| 1.6 | Activity chart has no cost overlay | Add optional `costUsd` field. Render as dashed line on secondary Y-axis. |
| 1.7 | System Health missing Job Queue | Add `{ key: 'job_queue', label: 'Job Queue', ... }` to `DASHBOARD_SUBSYSTEMS` in `dashboard-health.ts`. Source health from `jobsStats`. |
| 1.8 | System Health no error detail | For degraded/down subsystems, render `healthResult.message` or `healthResult.error` as a one-line description below the badge. |
| 1.9 | RecentActivityCard no severity filter | Add `ToggleBadgeGroup` with All/Critical/Warning/Info in card header. Filter displayed entries. Add severity count badges. |
| 1.10 | AlertsBanner no alert summaries | Pass `alerts[0].message` to `AlertsBanner`. Render inline: "3 critical — {message}" with timestamp. |
| 1.11 | AlertsBanner no quick-acknowledge | Add "Acknowledge All" ghost button calling `api.acknowledgeAlert` for each critical alert. |
| 1.12 | QuickActionsCard missing Monitoring | Add "Monitoring" tile linking to `/monitoring`. Conditionally render "Billing" if billing feature flag is enabled. |
| 1.13 | No auto-refresh | Add `useInterval(loadDashboardData, refreshInterval)` with configurable interval (default 60s). Show "Last updated X ago" in `DashboardHeader`. Add pause/resume toggle. |
| 1.14 | Storage progress bar lacks ARIA | Add `role="progressbar"`, `aria-valuenow={percent}`, `aria-valuemin={0}`, `aria-valuemax={100}`, `aria-label="Storage usage"` to the storage bar div in `StatsGrid.tsx`. |

---

## Stage 2: Identity & Access Management (~2 weeks)

> Addresses findings 2.1–2.13.

### Backend Work

| ID | Finding | API Changes |
|----|---------|-------------|
| 2.2 | MFA status N+1 calls | Add `include_mfa_status=true` query param to `GET /admin/users` that joins MFA enrollment status into user list response. Or add `GET /admin/users/mfa-status/bulk?ids=1,2,3`. |
| 2.6 | Org member search/pagination | Add `search`, `page`, `page_size` query params to `GET /admin/organizations/{id}/members`. |
| 2.10 | Registration code relocation | No backend change — existing endpoints work. This is a frontend restructuring. |

### Frontend Work

| ID | Finding | UI Changes |
|----|---------|------------|
| 2.1 | User table lacks Created At and MFA | Add "Created" column to user table. If bulk MFA endpoint available, render MFA badge (enabled/disabled/required) inline. |
| 2.2 | MFA N+1 calls | Replace `Promise.allSettled` fan-out with single bulk call. Remove the lazy per-user MFA fetch pattern. |
| 2.3 | No dormant account indicator | In user table, if `last_login_at` is >90 days ago (or null), render a red "Dormant" badge next to the Last Login cell. Make threshold configurable via constant. |
| 2.4 | Effective permissions lacks search | Add `<Input placeholder="Filter permissions..." />` above the permissions list in user detail. Add grouping by source (role / override / inherited) with collapsible headers. |
| 2.5 | Org detail too long without tabs | Refactor `organizations/[id]/page.tsx` into a tabbed layout using `<Tabs>`: Overview (org info, settings), Members, Teams, Keys & Secrets (BYOK), Billing (conditional). Each tab lazy-loads its content. |
| 2.6 | Org member table no search/pagination | Add search input + `<Pagination>` to the Members tab, using `useUrlPagination`. |
| 2.7 | Permission matrix lacks search/grouping | Add search input filtering permission rows. Group rows by namespace prefix (e.g., `read:`, `write:`, `manage:`). Add "Show differences only" toggle that hides rows where all roles have the same value. |
| 2.8 | Role comparison not discoverable | Add "Compare Roles" button to `roles/page.tsx` header alongside "Open Permission Matrix". |
| 2.9 | No bulk ops on orgs/teams | Add checkbox column + bulk action toolbar to `organizations/page.tsx` and `teams/page.tsx`. Actions: Bulk Delete (with confirm), Bulk Plan Assign (orgs, if billing). |
| 2.10 | Registration codes on dashboard | Extract registration code management from `app/page.tsx` into `app/users/registration/page.tsx`. Add nav item under Identity & Access. Keep a summary card + link on dashboard. |
| 2.11 | Teams no "All Teams" view | Add "All Organizations" option to org selector in `teams/page.tsx`. When selected, fetch teams across all orgs. |
| 2.12 | No Resend Invite action | Add Actions column to invitation table with "Resend" (pending/expired) and "Revoke" (pending) buttons. Wire to `api.createOrgInvite` (resend) and a new revoke endpoint. |
| 2.13 | Org detail raw `<select>` | Replace raw `<select>` elements in `organizations/[id]/page.tsx` with `<Select>` from `@/components/ui/select`. |

---

## Stage 3: API Key & Secret Management (~1.5 weeks)

> Addresses findings 3.1–3.11 (3.2 and 3.3 done in Stage 0).

### Backend Work

| ID | Finding | API Changes |
|----|---------|-------------|
| 3.6 | No per-key cost/usage | Add `GET /admin/api-keys/{id}/usage` returning request count, token count, estimated cost over a time range. Or include `usage_24h` in the unified key list response. |
| 3.7 | Expiration warnings passive only | Add server-side cron job that checks for keys expiring within 30/14/7/1 days and creates notification events (using existing notification channel system). |
| 3.8 | No audit trail on hub | Extend `GET /admin/audit` with `resource_type=api_key` filter if not already supported. |
| 3.9 | BYOK validation no per-key results | Add `GET /admin/byok/validation-runs/{id}/results` returning per-key validation status with error details. |
| 3.10 | Virtual keys no manage actions | Add `DELETE /admin/users/{id}/virtual-keys/{key_id}` and `POST /admin/users/{id}/virtual-keys/{key_id}/revoke`. |

### Frontend Work

| ID | Finding | UI Changes |
|----|---------|------------|
| 3.1 | Age thresholds no legend | Add tooltip on "Age" column header: "Green: <90 days, Yellow: 90-180 days, Red: >180 days". Use `<Popover>` with the age policy text. |
| 3.4 | No Create Key on hub | Add "Create API Key" button to hub page header. Open dialog with user selector (autocomplete) + key name/scope/expiry fields. On submit, call `api.createApiKey(userId, ...)`. |
| 3.5 | No bulk revoke | Add "Revoke Selected" button alongside "Rotate Selected" in the bulk actions bar. Wire to `api.revokeApiKey` for each selected key with `PrivilegedActionDialog`. |
| 3.6 | Per-key cost/usage | Add expandable row detail to `UnifiedApiKeysTable` showing usage chart (requests/tokens/cost over 7 days). |
| 3.7 | Expiration warnings passive | Add a banner at top of `/api-keys` page when any keys expire within 7 days: "N keys expiring within 7 days — [View]". Wire View to filter. |
| 3.8 | No audit trail on hub | Add "Recent Key Activity" collapsible section at bottom of `/api-keys` page, fetching from audit API with `resource_type=api_key` filter. |
| 3.9 | BYOK validation per-key results | After validation run completes, add "View Results" link that opens a dialog or navigates to a detail view showing per-key status. |
| 3.10 | Virtual keys no actions | Add Actions column to virtual keys table in `users/[id]/api-keys`: Delete (with confirm), Revoke. |
| 3.11 | New key dismiss no confirmation | Replace "Dismiss" with a two-step: first click changes to "Are you sure? Key will be hidden forever" with Copy + Dismiss buttons. Auto-copy to clipboard on key creation. |

---

## Stage 4: AI & Model Governance (~2 weeks)

> Addresses findings 4.2–4.15 (4.4 and 4.6 done in Stage 0).

### Backend Work

| ID | Finding | API Changes |
|----|---------|-------------|
| 4.2 | No provider budget thresholds | Add `provider_budgets` table and `GET/PUT /admin/providers/{name}/budget` endpoints (daily_limit_usd, monthly_limit_usd, alert_threshold_pct). Add cron check for threshold breaches. |
| 4.7 | ACP Sessions no cost | Add `estimated_cost_usd` field to ACP session response, computed from `total_tokens * model_price_per_token`. |
| 4.10 | MCP per-tool analytics | Add `GET /admin/mcp/tools/usage` returning per-tool invocation count, error count, avg latency, last invoked. |
| 4.12 | Voice command dry-run | Add `POST /admin/voice-commands/{id}/dry-run` that validates phrase match + action config (tool exists, config schema valid) without executing. Return validation result. |
| 4.15 | AI governance dashboard | Add `GET /admin/ai/overview` aggregating: total spend by provider, total tokens, active ACP sessions, top agents by cost, rate limit event count. |

### Frontend Work

| ID | Finding | UI Changes |
|----|---------|------------|
| 4.2 | Provider budget thresholds | Add "Budget" section to provider detail (expandable row or tab) with daily/monthly limit inputs and alert threshold slider. Highlight providers exceeding threshold in the list. |
| 4.3 | ACP Agent tool picker | Replace free-text `<Input>` for allowed/denied tools with a multi-select component. Fetch available tools from `api.getMCPTools()`. Show searchable checklist. |
| 4.5 | Agent policy raw JSON | Replace `<textarea>` with a dynamic form: repeating row of `[tool_pattern input] [tier dropdown: auto_approve|require_approval|deny] [remove button]`. Add "Add Rule" button. Show JSON preview in collapsible section. |
| 4.7 | ACP Sessions cost column | Add "Est. Cost" column to sessions table using `estimated_cost_usd` from response. Format as `$X.XX`. Highlight sessions exceeding configurable threshold (e.g., red if >$5). |
| 4.8 | ACP Sessions auto-refresh | Add `useInterval(loadSessions, 15000)` with pause/resume toggle. Show "Live" indicator when polling is active. |
| 4.9 | ACP Sessions raw user IDs | Replace `session.user_id` with a link: `<a href="/users/{id}">{username}</a>`. Fetch usernames via a batch lookup or include in session response. |
| 4.10 | MCP per-tool analytics | Add "Usage" column to Tools tab in `mcp-servers/page.tsx` showing invocation count, error rate, avg latency per tool. |
| 4.11 | Voice command test on list | Add "Test Phrase" input at top of `voice-commands/page.tsx` with a "Test" button. On submit, call test API and show which command matched (if any) with confidence score. |
| 4.12 | Voice command dry-run | Add "Dry Run" button on voice command detail page next to existing "Test Command". Call dry-run endpoint and display validation results (tool exists, config valid, etc.) with pass/fail badges. |
| 4.14 | Resource Governor raw user ID | Replace user ID `<Input>` in policy resolution tool with a user search autocomplete. Fetch users via `api.getUsers` with debounced search. |
| 4.15 | AI governance dashboard | Create `app/ai-overview/page.tsx` with: total spend card (by provider pie chart), token consumption trend line, active sessions count, top 5 agents by cost table, rate limit event summary. Add to sidebar under "AI & Models". |

---

## Stage 5: Operational Monitoring (~2 weeks)

> Addresses findings 5.1–5.16 (5.14 done in Stage 0).

### Backend Work

| ID | Finding | API Changes |
|----|---------|-------------|
| 5.4 | Dependencies only LLM | Add `GET /admin/dependencies/health` that checks all external services (database connectivity, cache ping, queue health, object storage) and returns status/latency per dependency. |
| 5.5 | Dependencies no history | Add `GET /admin/dependencies/history?provider={name}&range=30d` returning historical health check results. Store health check results in a time-series table. |
| 5.6 | Incidents no notification | Add `POST /admin/incidents/{id}/notify` that sends status update to assigned user + configured notification channels. Optionally auto-notify on status transitions via webhook. |
| 5.7 | Incidents no SLA tracking | Add computed fields to incident response: `time_to_acknowledge_seconds` (first status change after creation), `time_to_resolve_seconds` (resolved_at - created_at). Add `GET /admin/incidents/stats` returning aggregate MTTR/MTTA. |
| 5.11 | Audit-to-logs cross-ref | Add `request_id` field to audit log response (if available from backend audit events). |
| 5.12 | Compliance reports HTML-only | Add `format` query param to compliance report endpoint: `html`, `pdf`, `csv`, `json`. For PDF, use server-side rendering (e.g., Puppeteer or WeasyPrint). |

### Frontend Work

| ID | Finding | UI Changes |
|----|---------|------------|
| 5.1 | No monitoring auto-refresh | Add auto-refresh to `useMonitoringDataLoader` with configurable interval (default 60s). Show "Auto-refresh: ON" toggle in `MonitoringPageHeader`. |
| 5.2 | Alerts truncated to 10 | Replace `.slice(0, 10)` with `<Pagination>` in `AlertsPanel.tsx`. Show "Showing X of Y alerts" count. |
| 5.3 | Alert rule creation not discoverable | Add "Create Rule for This" action in alert row dropdown that navigates to AlertRulesPanel with metric pre-filled. Add "Create Rule" link at bottom of AlertsPanel. |
| 5.4 | Dependencies only LLM | Expand `dependencies/page.tsx` to include non-LLM services from new endpoint. Show database, cache, queue, storage health alongside providers. |
| 5.5 | Dependencies no history | Add 30/90-day uptime percentage badge per dependency. Add expandable history chart (sparkline of response times over time). |
| 5.6 | Incidents no notification | Add "Notify Team" button to incident detail (next to status dropdown). On status change, show "Notify stakeholders?" checkbox (default checked for severity >= high). |
| 5.7 | Incidents no SLA | Add "Time to Acknowledge" and "Time to Resolve" columns to incidents table. Add summary card at top: "Avg MTTR: Xh, Avg MTTA: Ym" for filtered incidents. |
| 5.8 | Incidents timeline collapsed | Change `<details>` to `<details open>` for incidents with status !== 'resolved'. Keep collapsed for resolved incidents. |
| 5.9 | Incidents no runbook | Add optional "Runbook URL" field to incident create/edit form. Render as external link icon next to incident title. |
| 5.10 | Jobs SLA no violation alerting | In jobs table, highlight rows where processing time exceeds SLA `max_processing_time_seconds` (red background). Add "SLA Breaches: N" badge on SLA policy card. |
| 5.11 | Audit-to-logs cross-ref | If `request_id` present on audit entry, add "View Related Logs" action that navigates to `/logs?requestId={id}`. On logs page, if `request_id` filter is active, add "View Audit Events" link. |
| 5.12 | Compliance reports | Add format selector (HTML/PDF/CSV/JSON) to compliance report generation dialog. Add "Schedule" option with frequency (weekly/monthly) and email recipient. |
| 5.13 | Compliance cap no warning | After report generation, if `events.length === COMPLIANCE_REPORT_LIMIT`, show yellow banner: "Report may be incomplete — reached 5000 event limit. Narrow the date range for complete data." |
| 5.15 | WatchlistsPanel raw `<select>` | Replace native `<select>` with `<Select>` from design system. |
| 5.16 | No URL state for monitoring | Use `useUrlMultiState` for time range, custom start/end dates, and active series toggles. Enables shareable monitoring URLs. |

---

## Stage 6: Governance & Compliance (~1.5 weeks)

> Addresses findings 6.1–6.11.

### Backend Work

| ID | Finding | API Changes |
|----|---------|-------------|
| 6.1 | Security risk N+1 sampling | Add `GET /admin/security/key-age-stats` returning aged key counts without per-user fan-out. Aggregated server-side. |
| 6.3 | Budget no forecasting | Add `GET /admin/budgets/{org_id}/forecast` returning current spend, burn rate, projected exhaustion date based on trailing 7-day average. |
| 6.5 | Usage no per-user/org cost | Add `GET /admin/usage/cost-attribution?group_by=user|org&range=7d` returning cost rollups per user or org. |
| 6.11 | No compliance posture | Add `GET /admin/compliance/posture` aggregating: MFA adoption %, encryption rotation status, retention compliance %, DSR fulfillment rate, audit log completeness score. |

### Frontend Work

| ID | Finding | UI Changes |
|----|---------|------------|
| 6.1 | Security N+1 | Replace `loadRiskBreakdownContext` fan-out with single call to new endpoint. Remove `MAX_USERS_FOR_KEY_SCAN` sampling logic. Show actual counts instead of estimates. Remove confidence caveat text. |
| 6.2 | Risk weights not configurable | Add "Configure Weights" button opening a dialog with sliders for each risk factor (MFA weight, Key Age weight, Failed Logins weight, Suspicious Activity weight) and their caps. Persist to backend settings. |
| 6.3 | Budget no forecasting | Add progress bar per budget showing current spend / limit. Add "Projected Exhaustion" date below each limit. Add mini sparkline showing 7-day spend trend. |
| 6.4 | Usage 8 tabs | Restructure into 2 tiers: Primary tabs (Status, Quota, Models) always visible. Secondary tabs (Providers, Access, Network, Conversations, Log) in a "More" dropdown or collapsible section. Default to Status tab. |
| 6.5 | Usage no cost attribution | Add "Cost by User" and "Cost by Organization" tabs (or sub-views within Status tab). Show ranked list with user/org name, total cost, token count, request count. |
| 6.6 | Cryptic abbreviations | Add `title` tooltips on PP ("Prompt Tokens") and TG ("Total Generated Tokens") column headers. On screens > 1024px, show full labels. |
| 6.7 | No A/B testing | Defer — document feature flags as a flag system, not an experimentation platform. Add a note in the flags page: "For A/B testing, use a dedicated experimentation platform." |
| 6.8 | Flags + maintenance combined | Move maintenance mode toggle from `flags/page.tsx` to `data-ops/page.tsx` (which already has a MaintenanceSection). Remove the redundant maintenance section from flags. |
| 6.9 | Retention preview no escalation | In `RetentionPoliciesSection.tsx`, add conditional styling on impact count: `> 1000` = red background + warning icon, `100-1000` = yellow, `< 100` = default. |
| 6.10 | GDPR DSR record-only | Add a prominent blue info banner at top of DSR section: "Record-only mode — requests are logged for manual processing. Automated execution coming in a future release." |
| 6.11 | No compliance posture | Create `app/compliance/page.tsx` with posture score card (0-100), dimension breakdown (MFA, encryption, retention, DSR, audit), trend chart, and per-dimension drill-down links. Add to sidebar under Governance. |

---

## Stage 7: Billing & Plans (~1.5 weeks)

> Addresses findings 7.1–7.9 (7.1 done in Stage 0).

### Backend Work

| ID | Finding | API Changes |
|----|---------|-------------|
| 7.5 | Subscription lifecycle | Add `GET /admin/billing/subscriptions/{id}/events` returning lifecycle events (creation, plan changes, payment attempts, status transitions) with timestamps. |
| 7.9 | Revenue analytics | Add `GET /admin/billing/analytics` returning MRR, subscriber counts by plan, churn rate (30d), trial conversion rate, revenue trend (30d daily). |

### Frontend Work

| ID | Finding | UI Changes |
|----|---------|------------|
| 7.2 | No plan comparison | Add "Compare Plans" toggle button on plans page. When active, switch from card grid to a comparison table: features as rows, plans as columns, with checkmarks for included features. |
| 7.3 | Overage rate no context | Below overage rate in plan card, add italic helper text: "e.g., 100k excess tokens = ${computed}". Calculate dynamically from the plan's rate. |
| 7.4 | Subscriptions no at-risk | Add "Needs Attention" section above the subscriptions table. Query for `status IN (past_due, incomplete)` and `trial_end < now + 7 days`. Show count badge and expandable list with "days past due" or "trial ends in N days". |
| 7.5 | Subscriptions no lifecycle | Make subscription table rows clickable. Navigate to `subscriptions/[id]/page.tsx` (new page) showing: current status card, lifecycle timeline (creation → plan changes → payments → status transitions), usage summary, invoices. |
| 7.6 | Org ID instead of name | In subscriptions table, resolve `org_id` to org name. Either join in backend response or batch-fetch orgs. Display: "Org Name (ID: N)" as link. |
| 7.7 | Feature registry no core vs gated | Add `availability_type` dropdown (Core / Plan-Gated / Add-on) per feature in the registry. Core features show as always-checked and grayed-out in the plan matrix. |
| 7.8 | Onboarding slug no uniqueness | Add debounced `api.checkSlugAvailability(slug)` call on slug input blur/change. Show inline green checkmark or red "Slug already taken" message. |
| 7.9 | No revenue analytics | Create `app/billing-analytics/page.tsx` (or tab within subscriptions). Cards: MRR, Active Subscribers, Churn Rate (30d), Trial Conversion Rate. Charts: Revenue trend (30d line chart), Subscribers by plan (donut), Churn events timeline. Add to sidebar under Governance (billing only). |

---

## Stage 8: System Config, Debug & Information Architecture Gaps (~1.5 weeks)

> Addresses findings 8.2–8.4 and 10.1–10.8.

### Backend Work

| ID | Finding | API Changes |
|----|---------|-------------|
| 8.3 | Debug only 2 tools | Add `GET /admin/debug/effective-permissions?user_id=X` (returns resolved permissions for user). Add `POST /admin/debug/validate-token` (decodes and validates JWT/session token). Add `GET /admin/debug/rate-limit-check?user_id=X&resource=Y` (simulates rate limit evaluation). |
| 10.1 | No webhook management | Add webhook CRUD endpoints: `GET/POST /admin/webhooks`, `GET/PUT/DELETE /admin/webhooks/{id}`, `GET /admin/webhooks/{id}/deliveries` (delivery log with status, response code, retry count). |
| 10.6 | No user invitation workflow | Add `POST /admin/users/invite` (email, role, org_id), `GET /admin/users/invitations` (pending/accepted/expired), `POST /admin/users/invitations/{id}/resend`, `DELETE /admin/users/invitations/{id}`. |

### Frontend Work

| ID | Finding | UI Changes |
|----|---------|------------|
| 8.2 | No environment indicator | Add environment badge to config page header. Source from `health.deployment_mode` or `process.env.NODE_ENV`. Show: "Production" (red), "Staging" (yellow), "Development" (green). |
| 8.3 | Debug only 2 tools | Add to `debug/page.tsx`: (1) Permission Resolver — user search input → display effective permissions with source (role/override/inherited). (2) Rate Limit Simulator — user + resource inputs → display applicable policies and whether request would be allowed/blocked. (3) Token Validator — paste JWT → show decoded payload, expiration status, issuer. |
| 8.4 | Debug raw API key only | Add "Lookup by Key ID" and "Lookup by User ID" tabs to existing debug tools. Query different endpoints based on selected mode. |
| 10.1 | No webhook management | Create `app/webhooks/page.tsx` with: webhook list table (URL, events, status, last delivery), create/edit dialog (URL, event types checklist, secret, active toggle), delivery log per webhook (expandable row showing request/response, status code, retry count). Add to sidebar under Operations. |
| 10.2 | No notification delivery | Add "Delivery Log" tab to monitoring NotificationsPanel showing: timestamp, channel, recipient, status (delivered/failed/pending), error message. Fetch from `api.getRecentNotifications()`. |
| 10.3 | No storage breakdown | Add "Storage" tab to Data Ops page showing: total usage, per-org breakdown (bar chart), per-category breakdown (backups, media, logs), growth trend line. |
| 10.4 | No error rate drill-down | Add "Error Analytics" section to monitoring page: error count by HTTP status code (bar chart), error count by endpoint (top 10 table), error trend line over selected time range. |
| 10.5 | No rate limit dashboard | Add "Rate Limit Analytics" section to resource-governor page: throttle events over time (line chart), top 5 throttled users (table), headroom utilization per policy (progress bars). |
| 10.6 | No user invitation workflow | Create `app/users/invitations/page.tsx` with: invitations table (email, role, org, status, sent date, accepted date), create invitation dialog (email, role, org selector), resend/revoke actions. Add nav link under Identity & Access. |
| 10.7 | No admin activity filter | Add "Admin Actions" saved search preset to audit page. Pre-filter: `actor_role IN (admin, super_admin, owner)`. Show as a tab or quick-filter button. |
| 10.8 | No scheduled reports | Add "Scheduled Reports" section to audit page (or a new Reports page). Config: report type (activity summary, access review, data access), frequency (daily/weekly/monthly), recipient email, format (HTML/PDF/CSV). CRUD for report schedules. |

---

## Stage 9: Accessibility & Cross-Cutting UX Polish (~1.5 weeks)

> Addresses findings 9.1–9.9 (9.5, 9.6, 9.8 done in Stage 0) and 11.1–11.9.

### Frontend Work — Cross-Cutting UX (Section 9)

| ID | Finding | UI Changes |
|----|---------|------------|
| 9.1 | Governance sidebar overloaded | In `lib/navigation.ts`, split "Governance" into "Cost & Usage" (budgets, usage, plans, subscriptions, feature-registry) and "Security & Compliance" (security, resource-governor, compliance, flags, data-ops). |
| 9.2 | Org context invisible to org-scoped | In `OrgContextSwitcher.tsx`, for non-super-admin users, render a read-only badge showing their org name instead of returning `null`. |
| 9.3 | No active org scope indicator | Add "Viewing: {orgName}" badge in page header area (in the layout component) when an org is selected. Show "Viewing: All Organizations" when global. |
| 9.4 | Shortcuts cover only 9 pages | In `use-keyboard-shortcuts.ts`, add: `g s` (security), `g j` (jobs), `g b` (budgets), `g i` (incidents), `g d` (data-ops), `g k` (api-keys), `g l` (logs), `g v` (voice-commands). Update help dialog. |
| 9.7 | No optimistic updates | Implement optimistic updates for: feature flag toggle (instant visual toggle, revert on error), incident status change, job retry/cancel, alert acknowledge/dismiss. Pattern: update local state immediately, fire API call, revert on failure with error toast. |
| 9.9 | Deprecated ConfirmDialog still used | Find all imports of `ConfirmDialog` and replace with `useConfirm()` pattern. Then delete `components/ui/confirm-dialog.tsx` deprecated export. |

### Frontend Work — Accessibility (Section 11)

| ID | Finding | UI Changes |
|----|---------|------------|
| 11.1 | Charts no text alternatives | For each Recharts component (`MetricsChart`, `TopCommandsChart`, `UsageTrendsChart`, activity chart in `ActivitySection`): wrap in `<div role="img" aria-label="{dynamic summary}">`. Generate summary string from latest data points (e.g., "CPU 45%, Memory 62%, trending stable"). Add collapsible `<Table>` fallback below each chart with the raw data. |
| 11.2 | ExportMenu not keyboard accessible | Rewrite `components/ui/export-menu.tsx` using `<DropdownMenu>` from Radix. Replace manual `isOpen` state and `<div onClick>` backdrop with `DropdownMenuTrigger/Content/Item`. |
| 11.3 | Keyboard chords conflict with screen readers | Remove `preventDefault()` from the initial `g` key press in `use-keyboard-shortcuts.ts`. Only `preventDefault()` on the second keypress (the actual shortcut). Add a "Disable keyboard shortcuts" toggle in user preferences (persisted to localStorage). |
| 11.4 | Loading states lack aria-live | Create `components/ui/loading-state.tsx` with `<div role="status" aria-live="polite">{children}</div>`. Replace all `<div>Loading...</div>` instances with `<LoadingState>`. (Many were fixed in Stage 0 with skeletons; this catches remaining inline loaders.) |
| 11.5 | Health status color-only | In `ActivitySection` health grid, replace color-only badges with `<StatusIndicator>` component which includes text + icon + color. |
| 11.6 | Toast container no aria-live | In `components/ui/toast.tsx`, add `aria-live="polite"` and `aria-relevant="additions"` to the toast container `<div>`. |
| 11.7 | Onboarding step indicator no a11y | Add `role="group"` and `aria-label="Onboarding progress, step {n} of 3"` to step indicator container. Add `aria-current="step"` to active step. Wrap step changes in `aria-live="polite"` region. |
| 11.8 | Flag history native `<details>` | Replace `<details><summary>` in flags page with a `Collapsible` component from the design system (or build one using Radix `Collapsible`). |
| 11.9 | Global error page no dark mode | Add `@media (prefers-color-scheme: dark)` block to inline styles in `global-error.tsx`. Dark palette: `background: '#1a1a2e'`, `color: '#e0e0e0'`, card `background: '#16213e'`. |

---

## Finding Coverage Matrix

All 120 findings are accounted for:

| Stage | Findings Addressed |
|-------|--------------------|
| 0 | 4.4, 4.6, 7.1, 9.6, 3.2, 3.3, 5.14, 9.5, 9.8 |
| 1 | 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 1.10, 1.11, 1.12, 1.13, 1.14 |
| 2 | 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10, 2.11, 2.12, 2.13 |
| 3 | 3.1, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 3.11 |
| 4 | 4.2, 4.3, 4.5, 4.7, 4.8, 4.9, 4.10, 4.11, 4.12, 4.14, 4.15 |
| 5 | 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 5.10, 5.11, 5.12, 5.13, 5.15, 5.16 |
| 6 | 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 6.10, 6.11 |
| 7 | 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 7.9 |
| 8 | 8.2, 8.3, 8.4, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8 |
| 9 | 9.1, 9.2, 9.3, 9.4, 9.7, 9.9, 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 11.8, 11.9 |

**Positive findings (no action):** 4.1, 4.13, 8.1

**Deferred (documented, not built):** 6.7 (A/B testing — out of scope, documented as feature-flag-only system)
