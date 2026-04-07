# Admin UI — HCI/Design Expert Review

**Date:** 2026-03-26
**Scope:** Full review of `./admin-ui` Next.js 15 webapp
**Tech stack:** Next.js 15 (App Router), React 19, Radix UI + Tailwind CSS 4, React Hook Form + Zod, Recharts, Lucide icons

---

## Section 1: Dashboard & At-a-Glance Overview

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 1.1 | No active-sessions KPI in StatsGrid | Important | Missing Functionality | 8 KPI cards: Users, Orgs, Providers, Storage, P95 Latency, Error Rate, Daily LLM Cost, Jobs & Queue. No active session count. | Add an "Active Sessions" card — critical for detecting abuse or credential-sharing. |
| 1.2 | No token-consumption KPI | Important | Information Gap | Daily LLM Cost tracked in dollars only. No token-level metric (prompt vs. completion breakdown). | Add a token-consumption card (total tokens/day with trend). Tokens are more tangible than cost for capacity planning. |
| 1.3 | Cache hit rate buried in System Health grid, not in KPIs | Nice-to-Have | Information Gap | Cache hit rate only shown as secondary text under "RAG Cache" in `ActivitySection`. | Promote to a top-level KPI or activity chart overlay — cache performance directly impacts latency and cost. |
| 1.4 | MCP tool invocation rates absent from dashboard | Nice-to-Have | Missing Functionality | No MCP tool usage metrics anywhere in dashboard components. | Add a KPI or trend indicator if the backend instruments MCP tool calls. |
| 1.5 | Activity chart lacks error-rate and latency overlays | Important | Information Gap | Area chart renders only `requests` and `users` series. Error rate and latency exist as KPIs but have no time-series visualization. | Add toggleable overlay lines for errors and latencyP95. Admins need to correlate request spikes with error/latency visually. |
| 1.6 | Activity chart has no cost overlay | Nice-to-Have | Information Gap | Daily cost is scalar-only; no cost-over-time series. | Add an optional cost sparkline or overlay. |
| 1.7 | System Health grid monitors 8 subsystems, not 9 — no Job Queue entry | Nice-to-Have | Information Gap | `DASHBOARD_SUBSYSTEMS` lists: API Server, Database, LLM, RAG, TTS, STT, Embeddings, RAG Cache. No "Job Queue / Worker" entry despite Jobs KPI existing. | Add a "Job Queue" subsystem to the health grid sourced from `jobsStats`. |
| 1.8 | System Health shows no response time or error detail | Important | UX/Usability Issue | Each subsystem row shows a colored icon, label, "Last checked" timestamp, and badge (Healthy/Degraded/Down). No latency or error message. | For degraded/down statuses, show a one-line reason or error message to enable triage without navigating to /monitoring. |
| 1.9 | RecentActivityCard has no severity filter | Important | UX/Usability Issue | Card shows up to 10 entries with severity icons but no filter controls. If all 10 are info-level, critical items are invisible. | Add a severity filter toggle and count badges per severity in the header. |
| 1.10 | AlertsBanner shows only aggregate counts, no alert summaries | Important | Information Gap | Banner shows "X critical, Y warning, Z info" and a link to /monitoring. No alert titles or messages shown. `DashboardAlert` type has `message` and `created_at` but these are lost in rendering. | Display at least the most recent or highest-severity alert message inline (e.g., "3 critical: 'Database connection pool exhausted'"). |
| 1.11 | AlertsBanner has no quick-acknowledge action | Nice-to-Have | Missing Functionality | Banner is purely informational — must navigate to /monitoring to act. | Add an "Acknowledge" or "Dismiss" button for batch alert management from the dashboard. |
| 1.12 | QuickActionsCard missing Monitoring shortcut | Nice-to-Have | UX/Usability Issue | 6 tiles: Manage Users, Organizations, API Keys, Audit Logs, Roles, Configuration. No Monitoring tile. | Add "Monitoring" — alert triage is a high-frequency admin workflow. Conditionally show "Billing" if enabled. |
| 1.13 | No auto-refresh / polling on the dashboard | Important | Missing Functionality | Dashboard data loads on mount and via manual Refresh button only. No periodic auto-refresh. | Add configurable auto-refresh (e.g., 60s) with a "Last updated X ago" indicator. Stale data on an ops dashboard is a significant risk. |
| 1.14 | Storage progress bar lacks ARIA semantics | Nice-to-Have | Accessibility Concern | Dashboard storage bar uses a `div` with inline width styling — no `role="progressbar"`, no aria attributes. `UserProfileCard` does this correctly. | Add `role="progressbar"` with `aria-valuenow/min/max/label` consistent with `UserProfileCard`. |

---

## Section 2: Identity & Access Management

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 2.1 | User table lacks "Created At" and inline MFA Status columns | Important | Information Gap | Columns: Checkbox, ID, Username, Email, Role, Status, Storage, Last Login, Actions. MFA status only appears when filter is toggled (triggering N+1 API calls). No "Created At". | Add "Created At" column. Surface MFA as a badge loaded in batch. |
| 2.2 | MFA status requires N+1 API calls | Important | UX/Usability Issue | When `mfaFilter !== 'all'`, individual `api.getUserMfaStatus(id)` fires for every user. 200 users = 200 parallel calls. | Request a bulk MFA status endpoint or include MFA in user list response. |
| 2.3 | No visual indicator for dormant accounts | Important | Information Gap | "Last Login" shows a date but no conditional styling for long-inactive accounts. | Add a "Dormant" badge or red highlight for accounts inactive >90 days. Critical for security audits. |
| 2.4 | Effective permissions list lacks search/filter | Nice-to-Have | UX/Usability Issue | User detail renders all effective permissions as a flat list with source labels. Hard to scan with many permissions. | Add search input and group by source (role-derived vs. overrides). |
| 2.5 | Organization detail page is too long without tabs | Important | UX/Usability Issue | Single scrollable view: header, Members, Teams, BYOK Keys, Watchlist Settings, and conditionally Billing/Usage/Invoices. 5-7 cards on one page. | Introduce tabs (Members, Teams, Keys & Secrets, Settings, Billing) to reduce cognitive load and initial load time. |
| 2.6 | Org detail member table has no search or pagination | Important | Missing Functionality | Members rendered inline with no search/filter/pagination. Unusable for orgs with hundreds of members. | Add search/filter and pagination matching the users list page pattern. |
| 2.7 | Permission matrix lacks search/filter and row grouping | Important | UX/Usability Issue | Full table with permissions as rows, roles as columns. No search, no namespace grouping, no "show differences only" toggle. Unwieldy at 50+ permissions × 10+ roles. | Add permission search, group by namespace prefix (read:, write:, admin:), add "differences only" toggle. |
| 2.8 | Role comparison page not discoverable from roles list | Important | UX/Usability Issue | Only linked from the matrix page header. No direct link from the roles list page. | Add "Compare Roles" button alongside "Open Permission Matrix" in the roles page header. |
| 2.9 | No bulk operations on organizations or teams | Important | Missing Functionality | Users have comprehensive bulk actions. Orgs and teams have none — each entity edited/deleted individually. | Add bulk delete at minimum. For orgs, consider bulk plan assignment if billing is enabled. |
| 2.10 | Registration code management lives on dashboard instead of IAM section | Important | UX/Usability Issue | Registration code CRUD is inline on `app/page.tsx` (lines 782-900+) making the dashboard 1000+ lines. Splits IAM across two locations. | Move to a dedicated `/users/registration` or `/settings/registration` page. Keep only a summary + link on dashboard. |
| 2.11 | Teams list has no "All Teams" view across orgs | Nice-to-Have | UX/Usability Issue | Auto-selects first org; no way to view teams across all orgs. | Add "All organizations" option for super-admins. |
| 2.12 | No "Resend Invite" action on invitation rows | Nice-to-Have | Missing Functionality | Invitation table shows status but no action column. No resend or revoke. | Add Actions column with Resend/Revoke options. |
| 2.13 | Org detail uses raw `<select>` instead of design system `<Select>` | Nice-to-Have | UX/Usability Issue | Raw HTML `<select>` for invite role and member role. Inconsistent with other pages using `@/components/ui/select`. | Replace with design system `Select` component. |

---

## Section 3: API Key & Secret Management

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 3.1 | Age column thresholds are hardcoded with no legend | Nice-to-Have | UX/Usability Issue | Green <90d, yellow 90-180d, red >180d. Thresholds are magic numbers in `api-keys-hub.ts`. No tooltip or legend explaining the bands. | Add a legend or tooltip near the "Age" column header explaining thresholds. |
| 3.2 | Key hygiene summary cards are not clickable | Important | UX/Usability Issue | "Needing Rotation", "Expiring Soon", "Inactive", "Hygiene Score" cards are static — clicking does not filter the table. | Make each card clickable to pre-apply the relevant filter. |
| 3.3 | 24h request count and error rate columns are permanently N/A | Important | Information Gap | Page banner states "24h request/error metrics are currently unavailable." `buildUnifiedApiKeyRows` hardcodes `null`. Two columns always show "N/A". | Either implement backend per-key telemetry or hide columns until data is available. Perpetual N/A degrades credibility. |
| 3.4 | No "Create Key" action on the hub page | Important | UX/Usability Issue | Key creation only possible from `/users/[id]/api-keys`. The hub has no create button — admin must navigate to user detail first. | Add a "Create Key" action (or prominent link) on the hub page. Consider a wizard for the full lifecycle. |
| 3.5 | No bulk revoke action | Nice-to-Have | Missing Functionality | Only "Rotate Selected" exists. No "Revoke Selected." | Add bulk revoke with danger confirmation — needed for emergency credential compromise response. |
| 3.6 | No per-key cost/usage attribution | Important | Missing Functionality | No cost or token usage columns anywhere in API key tables. | Add per-key usage attribution (requests, tokens, estimated cost) as expandable row detail or linked report. |
| 3.7 | Expiration warnings are passive only | Important | Missing Functionality | Expiry badges shown in table; "Expiring Soon" card counts them. No proactive notification (email, banner for imminent expiry). | Implement proactive alerting: email at 30/14/7/1 day thresholds, or dashboard-level banner for critically expiring keys. |
| 3.8 | No audit trail on the API keys hub | Important | Missing Functionality | No audit section showing who created/rotated/revoked which keys. | Add "Recent Key Activity" section or link to pre-filtered audit log. |
| 3.9 | BYOK validation shows only aggregate counts, not per-key results | Important | Information Gap | Validation run shows keys_checked/valid/invalid/errors. No drill-down to which specific keys failed. | After validation completes, link to individual key results with recommended actions. |
| 3.10 | Virtual API Keys have no manage actions | Important | Missing Functionality | Virtual keys table has no actions column. Once created, cannot be rotated, revoked, or deleted. | Add manage actions (at minimum delete/revoke). |
| 3.11 | New key dismiss has no "have you saved?" confirmation | Nice-to-Have | UX/Usability Issue | Single "Dismiss" click permanently hides the key. Accidental click = key lost forever. | Add confirmation before dismissing, or auto-copy to clipboard on creation. |

---

## Section 4: AI & Model Governance

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 4.1 | Providers page has excellent per-model usage metrics | -- | Strength | Comprehensive: requests, tokens, cost, error rate, latency per provider with expandable per-model drill-down, sparklines, cost formatting, deprecated model detection, provider test. | Gold standard for this admin UI. No changes needed. |
| 4.2 | No provider-level budget thresholds or spend alerts | Important | Missing Functionality | Cost is displayed but purely informational. No way to set limits or receive alerts when spending exceeds a threshold. | Add per-provider budget thresholds with alerting. Visually highlight providers exceeding a configurable warning level. |
| 4.3 | ACP Agents tool permissions use free-text input, no picker | Important | UX/Usability Issue | "Allowed Tools" and "Denied Tools" are plain `<Input>` with comma-separated values. No validation against available MCP tools. | Provide multi-select picker sourced from MCP tools catalog with search/filter. |
| 4.4 | ACP Agents have zero runtime usage metrics | Critical | Missing Functionality | Agent table columns: Name, Type, Status, Model, Tools, Actions. No request counts, token usage, error rates, or cost per agent. | Add per-agent usage metrics inline or as expandable detail. Without this, admins cannot assess ROI or detect misbehavior. |
| 4.5 | ACP Agent permission policy rules edited as raw JSON textarea | Important | UX/Usability Issue | Rules are a `<textarea>` expecting JSON array of `{tool_pattern, tier}`. Parse errors caught with toast but no schema guidance. | Replace with structured rule builder: repeatable form row with tool-pattern input and tier dropdown. Show JSON preview for power users. |
| 4.6 | ACP Sessions have no token budget or auto-termination | Critical | Missing Functionality | Token usage displayed as compact text. Sessions can only be manually closed. No maximum token budget per session. | Implement configurable per-session token limits with auto-termination and alerts. Show progress bar relative to configured cap. |
| 4.7 | ACP Sessions have no cost column | Important | Information Gap | Token counts shown but no cost estimation. Runaway agents invisible from a spending perspective. | Compute and display estimated cost per session based on model pricing. Highlight sessions exceeding thresholds. |
| 4.8 | ACP Sessions have no auto-refresh | Important | UX/Usability Issue | Page loads once on mount; manual refresh only. Inadequate for session monitoring. | Add auto-refresh (10-30s interval) or WebSocket live updates. |
| 4.9 | ACP Sessions show raw user IDs, not names | Nice-to-Have | UX/Usability Issue | User column shows numeric IDs with no link or name lookup. | Resolve to usernames and link to `/users/{id}`. |
| 4.10 | MCP Servers lack per-tool invocation analytics | Important | Missing Functionality | Module-level metrics (calls, errors, latency) exist. Tools tab shows only name, module, description — no invocation counts. | Add per-tool invocation counts, error rates, and latency. Essential for identifying failing or unused tools. |
| 4.11 | Voice Commands phrase test not available from list page | Nice-to-Have | UX/Usability Issue | Test facility only on detail page. Must navigate to each command to test. | Add global "Test phrase" input on list page showing which command would match. |
| 4.12 | Voice Commands lack action dry-run | Important | Missing Functionality | Test checks phrase matching only, not whether configured action would succeed (e.g., referenced MCP tool exists, config is schema-valid). | Add "Dry Run" that validates full pipeline: phrase match → action config validation, without executing side effects. |
| 4.13 | Resource Governor policy simulation is well-implemented | -- | Strength | "Simulate Impact" in policy form with server-side + client fallback, user/request impact counts. | No changes needed. |
| 4.14 | Resource Governor policy resolution requires raw user ID | Nice-to-Have | UX/Usability Issue | User ID input is plain text. No autocomplete or user lookup. | Add user search/autocomplete dropdown. |
| 4.15 | No centralized AI governance dashboard | Important | Missing Functionality | Each page (Providers, ACP Agents, ACP Sessions) has its own metrics but no single pane of glass for total AI spend, consumption, and trends. | Build an AI Operations summary: total spend by provider/agent/user, token trends, active sessions, rate limit event rate, top cost drivers. |

---

## Section 5: Operational Monitoring

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 5.1 | No auto-refresh for full monitoring dashboard | Important | Missing Functionality | Metrics chart polls every 5 minutes but alerts, system status, and watchlists load only on mount. Manual refresh required. | Add configurable auto-refresh (60s) for the full dashboard payload. |
| 5.2 | Alerts list truncated to 10 with no pagination or overflow indicator | Important | UX/Usability Issue | `AlertsPanel` hard-slices to 10 alerts. Remainder silently hidden. | Add pagination or "Load more" with visible "Showing 10 of N" count. |
| 5.3 | Alert rule creation not discoverable from alerts list | Important | UX/Usability Issue | AlertRulesPanel and AlertsPanel are separate cards with no cross-linking. No "Create rule for this metric" action on individual alerts. | Add "Create Rule" shortcut from AlertsPanel or contextual action that pre-fills rule draft. |
| 5.4 | Dependencies page covers only LLM providers | Important | Information Gap | Exclusively monitors LLM providers. Other subsystems (DB, RAG, TTS, STT, cache, queue) from SystemStatusPanel have no representation on Dependencies. | Expand to include all external dependencies or link to SystemStatusPanel for non-LLM services. |
| 5.5 | Dependencies lacks historical uptime tracking | Important | Missing Functionality | 7-day sparkline derived from usage aggregates. No persistent health check records. No SLA-style uptime percentage over 30/90 days. | Persist health checks server-side; add 30/90-day availability percentage and incident timeline per provider. |
| 5.6 | Incidents lack stakeholder notification | Important | Missing Functionality | Status changes, assignment, timeline, post-mortem — but no built-in mechanism to notify stakeholders on status transitions. | Add incident notification: auto-notify assigned users on transitions, or "Notify team" action button via configured channels. |
| 5.7 | Incidents lack SLA tracking (MTTR/MTTA) | Important | Missing Functionality | Tracks `created_at`, `updated_at`, `resolved_at` but no time-to-acknowledge, time-to-resolve, or SLA target comparison. | Add computed SLA metrics per incident and aggregate MTTR/MTTA on the list view. |
| 5.8 | Incidents timeline collapsed by default | Nice-to-Have | UX/Usability Issue | Timeline inside `<details>` — collapsed by default. For active incidents, timeline is the most important context. | Show timeline expanded by default for active (non-resolved) incidents. |
| 5.9 | Incidents lack runbook linking | Nice-to-Have | Missing Functionality | No field for linking to runbooks or SOPs. | Add optional `runbook_url` field and clickable link in UI. |
| 5.10 | Jobs SLA policies lack violation alerting | Important | Missing Functionality | Policies can be created with max processing/wait times and displayed with status badges. No UI for which jobs are currently breaching SLA. | Highlight breaching jobs in list; show breach counts on SLA card; optionally auto-create alerts for breaches. |
| 5.11 | Audit-to-Logs cross-referencing is one-directional | Important | Information Gap | `AuditLog` type has no `request_id`. Logs can correlate via request ID, but no link from audit events to related logs. | Add `request_id` to `AuditLog`; provide "View related logs" action on audit entries navigating to `/logs?requestId=<value>`. |
| 5.12 | Compliance reports HTML-only, not schedulable | Important | Missing Functionality | Generated on-demand as HTML blobs. No PDF, no CSV/JSON for compliance reports specifically, no scheduling. | Add PDF export, consider scheduling for recurring delivery. Add CSV/JSON for machine-readable compliance data. |
| 5.13 | Compliance reports capped at 5000 events with no warning | Nice-to-Have | Information Gap | `COMPLIANCE_REPORT_LIMIT = 5000`. No warning when limit is hit. | Display warning banner when report event count equals limit. |
| 5.14 | Alert icon-only buttons lack aria-labels | Nice-to-Have | Accessibility Concern | Acknowledge (checkmark) and Dismiss (X) buttons have `title` but no `aria-label`. | Add `aria-label` matching the `title` text. |
| 5.15 | WatchlistsPanel uses raw `<select>` instead of design system component | Nice-to-Have | UX/Usability Issue | Native `<select>` with inline Tailwind instead of `@/components/ui/select`. | Replace with design system `Select` for consistency. |
| 5.16 | No URL state for monitoring dashboard (not shareable) | Nice-to-Have | UX/Usability Issue | All state (time range, series visibility) in ephemeral React state. Cannot share or bookmark a monitoring view. | Persist time range and custom dates in URL params for shareability. |

---

## Section 6: Governance & Compliance

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 6.1 | Security risk breakdown relies on client-side N+1 sampling | Important | UX/Usability Issue | `loadRiskBreakdownContext()` fires up to 200 parallel `getUserApiKeys` calls to estimate key age across all users. Sample-based extrapolation may be inaccurate. | Move API key age calculation server-side. At minimum, add a confidence indicator (low/medium/high). |
| 6.2 | Risk factor weights hardcoded, not admin-configurable | Nice-to-Have | Information Gap | Weights: MFA=3/cap 40, Keys=2/cap 25, Failed logins=1/cap 20, Suspicious=4/cap 20. Formula visible but not adjustable. | Consider exposing weight/cap tuning in settings. |
| 6.3 | Budgets lack any forecasting or spend-trend visualization | Important | Missing Functionality | Flat CRUD table of per-org caps. No burn-rate projections, usage-over-time charts, or "days until exhaustion." | Add sparkline or progress bar showing current spend against cap, plus projected exhaustion date. |
| 6.4 | Usage page 8 tabs create high cognitive load | Important | UX/Usability Issue | 8 tabs: Status, Quota, Providers, Access, Network, Models, Conversations, Log. Each loads independently. | Group into primary (Status, Quota, Models) and secondary tiers. Or implement a summary dashboard as default. |
| 6.5 | Usage lacks per-user/per-org cost attribution | Important | Information Gap | Data scoped by time/provider/model/API key but no user-level or org-level cost rollup. | Add user/org attribution dimension. The quota tab has per-key `total_cost_usd` — need aggregate "user X spent $Y" view. |
| 6.6 | Usage column headers use cryptic abbreviations (PP, TG) | Nice-to-Have | UX/Usability Issue | "PP" (prompt tokens) and "TG" (total/generated tokens) without tooltips. | Add tooltips or legend. Full labels on wide screens, abbreviations on narrow. |
| 6.7 | Feature Flags: no A/B testing or experiment framework | Nice-to-Have | Missing Functionality | Single free-text variant per flag. No control/treatment groups or statistical tracking. | If A/B testing is in scope, add multi-variant support with traffic splitting. Otherwise document as feature-flag only. |
| 6.8 | Feature Flags and Maintenance Mode combined on one page | Nice-to-Have | UX/Usability Issue | Different audiences (product/eng vs. ops) and risk profiles. Data Ops also has a `MaintenanceSection`, creating redundancy. | Separate maintenance mode into Data Ops or its own page. |
| 6.9 | Retention policy impact preview lacks visual escalation for large deletions | Nice-to-Have | UX/Usability Issue | Deleting 10,000 records looks the same as deleting 10. Plain `<p>` with no severity styling. | Add red background for high-impact (>1000 records), yellow for moderate, default for low. |
| 6.10 | GDPR DSR erasure not actually executed (record-only mode) | Nice-to-Have | Information Gap | Success message states "not executed automatically in this release." May confuse admins. | Add prominent "Record-only mode" badge at top of section with roadmap link. |
| 6.11 | No compliance posture dashboard | Important | Missing Functionality | No page aggregates compliance across dimensions (MFA adoption, encryption rotation, retention compliance, DSR fulfillment, audit completeness). | Build Compliance Overview page aggregating posture metrics into a single score. |

---

## Section 7: Billing & Plans

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 7.1 | Plan deletion has no subscriber impact check | Critical | UX/Usability Issue | `handleDelete` deletes after generic confirm. No warning about or prevention of deleting plans with active subscribers. | Check and display active subscription count. Block deletion if subscribers exist or require migration first. |
| 7.2 | No side-by-side plan comparison view | Nice-to-Have | Missing Functionality | Card grid layout. No comparison table or diff for many plans. | Add "Compare plans" toggle switching to table with features as rows, plans as columns. |
| 7.3 | Overage rate implications not contextualized | Nice-to-Have | UX/Usability Issue | Shows `$X.XX/1k tokens` with no usage example. | Add contextual note: "At this rate, 100k excess tokens would cost $X." |
| 7.4 | Subscriptions lack at-risk identification | Important | Missing Functionality | Flat table with status filter. No visual distinction for past_due or expiring trials. No proactive surfacing. | Add "Needs attention" section showing past_due and high-usage subscriptions with "days since past_due" indicator. |
| 7.5 | Subscriptions lack lifecycle view | Important | Missing Functionality | Table shows current state only. No history of plan changes, payment failures, or renewal timeline. | Add subscription detail view showing lifecycle events: creation, plan changes, payment attempts, status transitions. |
| 7.6 | Subscriptions show "Org {id}" instead of org name | Nice-to-Have | UX/Usability Issue | `Org {sub.org_id}` rendered as link text. Admin must click through to identify org. | Display org name with ID in parentheses. |
| 7.7 | Feature Registry lacks core vs. gated distinction | Nice-to-Have | Missing Functionality | All features toggleable per-plan. No concept of "core" (always-available) vs. "gated" vs. "add-on." | Add `availability_type` field and visually distinguish core features (grayed-out, always-checked). |
| 7.8 | Onboarding: no slug uniqueness check before submission | Nice-to-Have | UX/Usability Issue | Regex validation only. Admin can reach Confirm step only to fail on duplicate slug. | Add debounced uniqueness check with inline feedback. |
| 7.9 | No revenue analytics, churn, or trial conversion metrics | Important | Missing Functionality | No aggregate business metrics anywhere. Individual subscriptions visible but no MRR, churn rate, or conversion funnel. | Add Billing Analytics dashboard: MRR, subscriber counts by plan, churn rate, trial conversion, revenue trend. |

---

## Section 8: System Configuration & Debug

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 8.1 | Config page is comprehensive and well-labeled | -- | Strength | Shows: auth mode, storage backend, features, providers, services, server version/uptime. All read-only with links to management pages. | No changes needed. |
| 8.2 | No active environment/profile indicator | Nice-to-Have | Information Gap | No indication of active config profile (dev/staging/prod) or config source (file, env vars, defaults). | Show prominent environment badge at top. Fall back to detected source if deployment_mode is empty. |
| 8.3 | Debug page has only 2 tools | Important | Missing Functionality | Only API Key Resolver and Budget Summary. Both require raw API key input. | Add: Permission Resolver (user ID → effective permissions), Rate Limit Simulator, Token Validator (decode JWT), Config Dump (sanitized). |
| 8.4 | Debug requires raw API key, not key ID or user ID | Nice-to-Have | UX/Usability Issue | Admin must paste actual API key string. Operationally awkward when you have a key ID but not the raw key. | Add alternative lookup modes: "by Key ID" or "by User ID." |

---

## Section 9: Cross-Cutting UX Concerns

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 9.1 | Governance sidebar section overloaded (9 items) | Nice-to-Have | UX/Usability Issue | Mixes security, billing, usage, data ops, and flags. | Split into "Cost & Usage" and "Security & Compliance." |
| 9.2 | Org context switcher invisible to org-scoped users | Nice-to-Have | UX/Usability Issue | Returns `null` for non-super-admins. Org-scoped users auto-selected but see no confirmation of which org they're scoped to. | Show read-only org name badge in sidebar for org-scoped users. |
| 9.3 | No visual indicator of active org scope in main content | Nice-to-Have | UX/Usability Issue | Switching orgs silently filters data with no confirmation feedback on the page. | Add "Viewing: [Org Name]" indicator near page header. |
| 9.4 | Keyboard shortcuts cover only 9 of 30+ pages | Nice-to-Have | UX/Usability Issue | `g+h`, `g+u`, `g+o`, `g+t`, `g+r`, `g+a`, `g+m`, `g+p`, `g+c`. No shortcuts for Security, Budgets, Jobs, Incidents, Data Ops, etc. | Add shortcuts for remaining high-traffic pages. |
| 9.5 | Inconsistent loading states across pages | Important | UX/Usability Issue | Skeleton components exist and used on ~13 pages. But many pages use bare `<div>Loading...</div>`: security, providers, roles/[id], roles/matrix, users/[id]/api-keys, organizations/[id], teams/[id], monitoring sub-panels. | Replace all bare "Loading..." with appropriate skeleton components. The library already covers these cases. |
| 9.6 | PrivilegedActionDialog only used in user management | Important | UX/Usability Issue | `usePrivilegedActionDialog` in `users/page.tsx` and `users/[id]/page.tsx` only. Destructive ops elsewhere (deleting budgets, policies, flags, BYOK keys, backup schedules) use `useConfirm()` without password re-auth or audit reason. | Apply `PrivilegedActionDialog` consistently to all destructive admin operations. Any `variant="danger"` confirm dialog should use privileged action dialog instead. |
| 9.7 | No optimistic updates anywhere | Nice-to-Have | UX/Usability Issue | All mutations follow fetch-then-refetch. Zero optimistic update patterns. | For low-risk ops (toggling flags, changing status), implement optimistic updates. Keep refetch for destructive ops. |
| 9.8 | Export only available on 2 of 12+ list pages | Important | Missing Functionality | `ExportMenu` on `users` and `audit` only. Missing on: organizations, teams, api-keys, logs, budgets, incidents, jobs, voice-commands, acp-sessions, subscriptions. | Add `ExportMenu` to all list pages that need data export. |
| 9.9 | Deprecated `ConfirmDialog` and newer `useConfirm()` both in use | Nice-to-Have | UX/Usability Issue | Visual inconsistency between the two patterns. | Fully migrate to `useConfirm()` and remove deprecated component. |

---

## Section 10: Information Architecture Gaps

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 10.1 | No webhook/integration management | Important | Missing Functionality | No page for managing outgoing webhooks, HTTP integrations, or event subscriptions. Monitoring NotificationsPanel handles alert channels but not general-purpose webhooks. | Add Webhooks/Integrations page: CRUD for endpoints, delivery status with retry, event type subscriptions. |
| 10.2 | No notification delivery status view | Nice-to-Have | Missing Functionality | NotificationsPanel manages channels with test-send but no delivery logs, bounce/failure rates. | Add delivery status tab or standalone log page. |
| 10.3 | No storage usage breakdown beyond StatsGrid | Nice-to-Have | Missing Functionality | Single "Storage" stat card. Monitoring shows disk % over time. No per-org, per-table, or per-category breakdown. | Add storage detail view (tab on Data Ops or dashboard section) with per-org storage and growth trends. |
| 10.4 | No error rate drill-down beyond StatsGrid | Nice-to-Have | Missing Functionality | Error Rate as summary stat only. No breakdown by endpoint, error type, or time window. | Add error analytics section to Monitoring with filterable breakdowns. |
| 10.5 | No rate limit monitoring dashboard | Nice-to-Have | Missing Functionality | Resource Governor shows recent events. No charts for throttle events over time, top-throttled users, or headroom utilization. | Add rate-limit analytics section: trend charts, top-throttled users, headroom per policy. |
| 10.6 | No general user invitation workflow (independent of billing) | Nice-to-Have | Missing Functionality | Onboarding wizard is billing-gated. No invite-by-email, no pending invitations list beyond registration codes. | Add user invitation workflow: invite by email, track pending/accepted/expired, resend capability. |
| 10.7 | No admin-specific activity filter | Nice-to-Have | Missing Functionality | Audit shows all events. No pre-filtered "Admin Actions" view for reviewing other admins' changes. | Add "Admin Actions" filter preset on Audit Logs page. |
| 10.8 | No scheduled reports or email digests | Nice-to-Have | Missing Functionality | No references to scheduled reports anywhere. | Add Reports section with daily/weekly email digest scheduling. |

---

## Section 11: Accessibility

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 11.1 | Recharts charts have no text alternative or data table fallback | Important | Accessibility Concern | All chart components render SVG without `aria-label`, `role="img"`, or tabular fallback. Screen readers get no meaningful information. | Wrap charts in `role="img"` with descriptive `aria-label`. Provide collapsible data table alternative below each chart. |
| 11.2 | ExportMenu is not keyboard accessible | Important | Accessibility Concern | Manual dropdown with `<div onClick>` backdrop. No `role="menu"`, no `aria-haspopup`, no keyboard arrow-key navigation, no focus management. | Rewrite using Radix `DropdownMenu` component for full ARIA menu pattern. |
| 11.3 | Keyboard chord system may conflict with screen reader keys | Nice-to-Have | Accessibility Concern | `g` key captured globally with `preventDefault()`. Screen readers (NVDA/JAWS) use single-letter keys for navigation. Could conflict. | Don't `preventDefault()` on initial `g`. Add preference to disable shortcuts entirely. Consider requiring modifier key (Alt+G). |
| 11.4 | Many loading states lack `aria-live` regions | Nice-to-Have | Accessibility Concern | 15+ instances of `<div>Loading...</div>` without `aria-live` or `role="status"`. Screen readers not notified of content change. | Wrap all loading indicators in `<div role="status" aria-live="polite">`. Create reusable `LoadingState` component. |
| 11.5 | Status indicators in dashboard health rely on color alone in some contexts | Nice-to-Have | Accessibility Concern | `ActivitySection` health badges and `getHealthIcon` use color differentiation (green/yellow/red) without consistent text labels. `StatusIndicator` component does this correctly but isn't used everywhere. | Use `StatusIndicator` consistently in dashboard health section or ensure all badges have text labels. |
| 11.6 | Toast container lacks `aria-live` on wrapper | Nice-to-Have | Accessibility Concern | Individual toasts have `role="alert"` but container div has no `aria-live`. Dynamic injection may be missed. | Add `aria-live="polite"` and `aria-relevant="additions"` to toast container. |
| 11.7 | Onboarding step indicator lacks accessible progress | Nice-to-Have | Accessibility Concern | Visual circles (blue/green/gray) with no `aria-current="step"`, no `role="progressbar"`, no screen reader announcement of step changes. | Add `aria-current="step"`, `role="group"` with `aria-label="Step 2 of 3"`, and `aria-live` region for step changes. |
| 11.8 | Feature flag history uses native `<details>` inconsistent with design system | Nice-to-Have | Accessibility Concern | `<details><summary>` element. Visually inconsistent. May not be styled/announced correctly by all screen readers. | Replace with design system disclosure component. |
| 11.9 | Global error page has no dark mode support | Nice-to-Have | Accessibility Concern | `global-error.tsx` uses hardcoded light colors. Jarring for users with dark mode preference or light sensitivity. | Add `prefers-color-scheme: dark` media query to inline styles. |

---

## Executive Summary

### Top 5 Critical Gaps That Would Block Admin Adoption

1. **ACP Agents have zero runtime metrics** (4.4) — Admins cannot assess agent ROI, detect misbehavior, or attribute costs to agents. This is a blind spot in AI governance.

2. **ACP Sessions have no auto-termination or token budgets** (4.6) — A runaway agent can consume unlimited tokens with no automatic safeguard. Combined with no auto-refresh (4.8), this is an operational risk.

3. **Plan deletion doesn't check for active subscribers** (7.1) — Deleting a plan with active subscribers could break billing for affected organizations.

4. **No dashboard auto-refresh** (1.13) — An operations dashboard showing stale data without warning undermines trust. Admins may act on outdated information.

5. **PrivilegedActionDialog inconsistently applied** (9.6) — Destructive operations in most areas (budgets, policies, flags, BYOK keys) lack audit reason and password re-auth, while user management has it. Creates an uneven security posture.

### Top 5 Quick Wins (High Impact, Low Effort)

1. **Make key hygiene summary cards clickable** (3.2) — Cards already exist and display counts. Wire `onClick` to set table filters. ~30 minutes of work.

2. **Replace bare "Loading..." with existing skeletons** (9.5) — Skeleton components already exist for every needed pattern. Just swap the JSX. ~2 hours.

3. **Add `ExportMenu` to remaining list pages** (9.8) — Component already exists and works. Drop it into 10+ pages. ~1-2 hours.

4. **Hide permanently-N/A API key columns** (3.3) — Two columns always showing "N/A" waste space and erode trust. Conditionally render based on data availability. ~15 minutes.

5. **Add `aria-label` to icon-only alert buttons** (5.14) — Copy existing `title` text to `aria-label`. ~15 minutes.

### Priority Roadmap

**Phase 1 — Safety & Trust (Weeks 1-2)**
- Fix plan deletion subscriber check (7.1)
- Apply PrivilegedActionDialog consistently (9.6)
- Add dashboard auto-refresh (1.13)
- Add ACP session token budgets + auto-termination (4.6)
- Implement all quick wins above

**Phase 2 — AI Governance (Weeks 3-4)**
- Add ACP Agent runtime metrics (4.4)
- Add ACP Session auto-refresh and cost column (4.7, 4.8)
- Add per-tool MCP invocation analytics (4.10)
- Build AI Operations summary dashboard (4.15)
- Add provider budget thresholds (4.2)

**Phase 3 — Operational Maturity (Weeks 5-6)**
- Add monitoring auto-refresh (5.1)
- Improve alert discoverability and pagination (5.2, 5.3)
- Expand Dependencies page beyond LLM providers (5.4)
- Add incident SLA tracking and notifications (5.6, 5.7)
- Add audit-to-logs cross-referencing (5.11)

**Phase 4 — Cost & Compliance (Weeks 7-8)**
- Add budget forecasting/trends (6.3)
- Restructure Usage page IA (6.4)
- Add per-user/per-org cost attribution (6.5)
- Build compliance posture dashboard (6.11)
- Add subscription lifecycle view and at-risk identification (7.4, 7.5)

**Phase 5 — Polish & Accessibility (Weeks 9-10)**
- Chart accessibility (text alternatives, data tables) (11.1)
- ExportMenu keyboard accessibility (11.2)
- Org detail tabs (2.5)
- Permission matrix search/grouping (2.7)
- Registration code management relocation (2.10)
- Revenue analytics and billing insights (7.9)
