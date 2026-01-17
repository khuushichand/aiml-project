## Stage 1: Org-Scoped Admin Enforcement + Org Context UI Alignment
**Goal**: Enforce org scoping server-side and ensure the org selector is an explicit super-admin filter.
**Success Criteria**:
- Admin endpoints enforce org membership for non‑platform admins (users/orgs/teams/usage/audit).
- Super admins can filter by org via `org_id` without bypassing server enforcement.
- Org context UI is hidden for org-scoped admins and behaves as a filter for super admins.
**Tests**:
- Unit: org scope guards for admin endpoints.
- Integration: list users/orgs/teams/usage/audit are scoped by org membership.
- UI: org selector appears only for super admins; lists reflect selected org.
**Status**: Complete

---

## Stage 2: User Picker + Global User Lifecycle Actions (Users UI)
**Goal**: Replace ID-based member adds and provide global user lifecycle controls in the Users page.
**Success Criteria**:
- Org/Team member adds use a searchable user picker (name/email) with validation.
- Users page supports create, activate/deactivate, and delete actions.
- Users list respects org scope when a super-admin org filter is selected.
**Tests**:
- Unit: user picker search/select behavior.
- Integration: create user; add user to org/team from picker.
- UI: bulk lifecycle actions render and operate as expected.
**Status**: Complete

---

## Stage 3: Admin Security Controls + Audit Log Drilldowns
**Goal**: Add admin-facing security controls and investigation tooling.
**Success Criteria**:
- MFA status visible per user; admin can disable MFA.
- Admin can list and revoke user sessions (single + revoke all).
- Audit logs support drill-down view with raw JSON copy and related links.
**Tests**:
- Unit: MFA/session admin endpoints.
- Integration: session revoke + MFA disable.
- UI: audit detail drawer renders large payloads without truncation.
**Status**: Complete

---

## Stage 4: Provider Management Controls + Jobs Actions UI
**Goal**: Make providers and jobs operable from the admin UI.
**Success Criteria**:
- LLM providers can be enabled/disabled, configured, allowlisted, and health‑checked.
- Jobs UI supports detail view, payload/result inspection, and actions (retry/cancel/requeue).
- Jobs actions use existing admin endpoints; missing ones are added.
**Tests**:
- Unit: provider config update validation; jobs action request builders.
- Integration: jobs retry/cancel/requeue flows; provider health check.
- UI: confirmations and error states for actions are handled.
**Status**: Complete

---

## Stage 5: Ops Governance Toolkit (Billing/Retention/Logs/Flags)
**Goal**: Deliver the expected admin control panel capabilities for operations and governance.
**Success Criteria**:
- Billing/quota governance: plans, budgets, alerts, per‑org spend caps.
- Data ops: backup/restore, retention policies, export tools beyond CSV.
- System ops: centralized logs viewer, incident history, maintenance mode, feature flags.
**Tests**:
- Unit: policy validation for retention/budget caps.
- Integration: backup/restore workflow; feature flag propagation.
- UI: logs viewer and incident timeline render large datasets smoothly.
**Status**: In Progress

### Summary
Provide a first-class operations console for platform admins to govern spend, retention, and platform runtime behavior without manual DB changes or ad‑hoc scripts.

### Users and Use Cases
- Platform admin: enforce budgets, set retention windows, and toggle maintenance or flags during incidents.
- Security/compliance reviewer: audit retention policies and access logs.
- Ops engineer: capture a backup before risky changes; review incidents and system logs.

### Functional Requirements
#### Billing & Quota Governance
- Display per‑org plan, current spend/usage, and budget thresholds.
- Configure per‑org spend caps with alert thresholds (e.g., 50/80/100%).
- Support both soft caps (warn) and hard caps (block) when the backend supports it.
- Show audit trail of budget changes (who/when).

#### Data Ops
- Backup creation on demand with status tracking and retention of snapshots.
- Restore workflow with explicit confirmation and warning banners.
- Retention policy editor by dataset (media, chats/notes, audit logs).
- Export tools for audit logs, users, and usage (CSV/JSON, server‑side for large datasets).

#### System Ops
- Logs viewer with filters (time range, severity, service, org/user id).
- Incident timeline with status, tags, and links to related logs.
- Maintenance mode toggle with optional user‑facing message and allowlist bypass.
- Feature flag console with scopes (global/org/user) and change history.

### UX/IA Notes
- Add an "Ops" section in the admin sidebar with subpages: Billing, Data Ops, Logs, Flags, Incidents.
- Use destructive confirmations for restore, maintenance mode, and hard‑cap changes.
- Prefer server‑side pagination for logs/exports; show "large dataset" warnings when needed.

### Permissions & Scoping
- Platform admins manage all orgs; org admins see read‑only summaries for their org.
- Destructive actions (restore, maintenance mode, hard caps) require explicit confirmation and audit logs.

### API Contract (aligned to current backend + gaps)
#### Existing endpoints (implemented)
- Billing/usage (admin, prefixed with `/api/v1/admin`):
  - GET `/api/v1/admin/budgets`
  - POST `/api/v1/admin/budgets`
  - GET `/api/v1/admin/usage/daily`
  - GET `/api/v1/admin/usage/top`
  - POST `/api/v1/admin/usage/aggregate`
  - GET `/api/v1/admin/usage/daily/export.csv`
  - GET `/api/v1/admin/usage/top/export.csv`
  - GET `/api/v1/admin/llm-usage`
  - GET `/api/v1/admin/llm-usage/summary`
  - GET `/api/v1/admin/llm-usage/top-spenders`
  - POST `/api/v1/admin/llm-usage/aggregate`
  - GET `/api/v1/admin/llm-usage/export.csv`
  - POST `/api/v1/admin/llm-usage/pricing/reload`
- Logs and stats:
  - GET `/api/v1/admin/audit-log`
  - GET `/api/v1/admin/stats`
- Cleanup controls:
  - GET `/api/v1/admin/cleanup-settings`
  - POST `/api/v1/admin/cleanup-settings`
- Resource governance policies (admin):
  - GET `/api/v1/resource-governor/policy` (snapshot)
  - GET `/api/v1/resource-governor/policies` (list)
  - GET `/api/v1/resource-governor/policy/{policy_id}`
  - PUT `/api/v1/resource-governor/policy/{policy_id}`
  - DELETE `/api/v1/resource-governor/policy/{policy_id}`
- Monitoring alerts (requires `system.logs` permission):
  - GET `/api/v1/monitoring/alerts`
  - POST `/api/v1/monitoring/alerts/{alert_id}/read`
  - GET/POST `/api/v1/monitoring/watchlists`
  - DELETE `/api/v1/monitoring/watchlists/{watchlist_id}`
  - POST `/api/v1/monitoring/reload`

#### Gaps / new endpoints required
- Plan governance: plan assignment and plan/limit overrides beyond budget settings.
- Usage summaries by org plan/cap with soft/hard enforcement signals.
- Backup/restore: create, list, and restore snapshots (no admin backup endpoints exist today).
- Retention policies by dataset (no admin retention endpoints exist today).
- Logs feed: filterable system log stream (audit logs exist, but no general logs endpoint).
- Incidents: CRUD for incident history (no admin incidents endpoint exists today).
- Maintenance mode: toggle + message + allowlist (no admin maintenance endpoint exists today).
- Feature flags: list/update with scope (no admin feature flag endpoint exists today).
- Export endpoints for audit logs and user lists (CSV/JSON). Usage exports are CSV-only today.

### Implementation Stages (Stage 5.x)
#### Stage 5.1: Billing and Usage Console (read-only first)
**Goal**: Deliver spend visibility and exports using the existing usage and LLM usage endpoints.
**Success Criteria**:
- Usage, LLM usage, and top spenders views are wired to existing admin endpoints.
- CSV exports for usage and LLM usage are accessible from the UI.
- Budget controls render in read-only mode or behind a feature flag until backend support lands.
**Tests**:
- Integration: usage, LLM usage, and CSV export requests.
- UI: tables paginate and filters render consistently across org scopes.
**Owner**: Admin UI (primary), Backend (support)
**Timeline**: 1 sprint
**Status**: Complete

#### Stage 5.2: Data Ops (backups, retention, exports)
**Goal**: Provide backup/restore workflows, retention policy editing, and expanded exports.
**Success Criteria**:
- Backup create/list/restore endpoints and UI workflows exist.
- Retention policy CRUD exists for core datasets.
- Audit log and user list export endpoints (CSV/JSON) are implemented and wired.
**Tests**:
- Integration: backup/restore flows; retention updates; export downloads.
- UI: destructive confirmations and status tracking render correctly.
**Owner**: Backend (primary), Admin UI (secondary)
**Timeline**: 1-2 sprints
**Status**: Complete

#### Stage 5.3: System Ops (logs, incidents, maintenance, flags)
**Goal**: Add operational controls for logs, incidents, maintenance, and feature flags.
**Success Criteria**:
- Filterable system logs feed supports large datasets.
- Incident history CRUD and timeline UI exist.
- Maintenance mode and feature flag endpoints are implemented and surfaced in the UI.
**Tests**:
- Integration: log queries; maintenance/flag toggles; incident create/update.
- UI: log viewer and incident timeline remain performant with large results.
**Owner**: Backend (primary), Admin UI (secondary)
**Timeline**: 1-2 sprints
**Status**: Complete

### Data Model Notes
- Retention policies should include dataset key, duration, and enforcement mode.
- Feature flags should include key, scope, value, updated_by, updated_at.
- Backups should include id, created_at, status, size, storage_url.

### Audit & Observability
- All updates in Stage 5 must emit audit events with org_id and actor_id.
- Logs viewer should surface request id / trace id when available.

### Edge Cases
- Restore in progress: block other destructive actions.
- Hard caps enabled while an org is already over budget.
- Retention policy conflicts (e.g., shorter than legal minimums).

### Open Questions
- Should backups be stored locally only or support external storage targets?
- What is the minimal acceptable logs retention window for compliance?
- Which roles can bypass maintenance mode?
