# Phase 2: Admin UI Sprint — Surface Backend Capabilities

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build 5 missing admin pages and 2 enhanced features to surface the 100+ backend admin endpoints that currently have no UI.

**Architecture:** Each page follows the established pattern: Next.js page wrapper (`pages/admin/*.tsx` with SSR disabled) + shared React component (`packages/ui/src/components/Option/Admin/*.tsx`) using Ant Design, React hooks for state, and `tldwClient` API methods. New API client methods are added per page.

**Tech Stack:** Next.js, React 18, TypeScript, Ant Design 5, TldwApiClient

---

## Pattern Reference

All new pages MUST follow these patterns from `ServerAdminPage.tsx`:

1. **Page wrapper**: `export default dynamic(() => import("@/routes/..."), { ssr: false })`
2. **Admin guard**: `deriveAdminGuardFromError()` for 403/404 handling
3. **State management**: `useState` hooks per data domain (data, loading, error)
4. **Initial load**: `useEffect` with `initialLoadRef` + cleanup cancellation
5. **Tables**: Ant Design `Table` with column defs, inline editing (Select, Switch), pagination
6. **Forms**: Ant Design `Form` with `validateFields()` + async submission
7. **Error display**: `sanitizeAdminErrorMessage()` for user-facing errors
8. **Reusable components**: `StatusBanner`, `CollapsibleSection` from existing library

---

## Task Overview

| Task | Gap | Page | Backend Endpoints | Effort |
|------|-----|------|-------------------|--------|
| 1 | 1.9 | API Key Management | 8 endpoints | S |
| 2 | 1.3 | Maintenance | 27 endpoints | M |
| 3 | 1.8 | Monitoring/Alerting | 8+ endpoints | M |
| 4 | 1.7 | Usage Analytics | 14+ endpoints | M |
| 5 | 1.1 | Orgs/Teams Management | 17 endpoints | L |
| 6 | 1.2 | Data Ops | 24+ endpoints | L |
| 7 | 1.6 | RBAC/Permissions Editor | 28 endpoints | L |

Tasks ordered by effort (smallest first) to build momentum and establish patterns.

---

## Task 1: API Key Management Panel (Gap 1.9)

**Files:**
- Create: `apps/packages/ui/src/components/Option/Admin/ApiKeyManagementPage.tsx`
- Create: `apps/tldw-frontend/pages/admin/api-keys.tsx`
- Create: `apps/tldw-frontend/routes/option-admin-api-keys.tsx`
- Modify: `apps/packages/ui/src/services/tldw/TldwApiClient.ts` (add API key methods)

**Backend endpoints to surface:**
- `GET /api/v1/admin/users/{user_id}/api-keys` — List keys
- `POST /api/v1/admin/users/{user_id}/api-keys` — Create key
- `DELETE /api/v1/admin/users/{user_id}/api-keys/{key_id}` — Revoke key
- `PATCH /api/v1/admin/users/{user_id}/api-keys/{key_id}` — Update limits
- `POST /api/v1/admin/users/{user_id}/api-keys/{key_id}/rotate` — Rotate key
- `POST /api/v1/admin/users/{user_id}/virtual-keys` — Create virtual key
- `GET /api/v1/admin/users/{user_id}/virtual-keys` — List virtual keys
- `GET /api/v1/admin/api-keys/{key_id}/audit-log` — Key audit log

**UI Layout:**
```
PageShell
├── Admin Guard
├── Page Title: "API Key Management"
├── User Selector (search users, pick one)
├── API Keys Table
│   ├── Columns: Name, Key Preview, Rate Limit, Allowed IPs, Created, Status
│   ├── Actions: Rotate, Edit Limits, Revoke
│   └── "Create Key" button → modal form
├── Virtual Keys Table (if org scoping enabled)
│   ├── Columns: Name, Org, Team, Created
│   └── "Create Virtual Key" button → modal form
└── Key Audit Log (expandable per key)
```

**Step 1:** Add API client methods to `TldwApiClient.ts`
**Step 2:** Create `ApiKeyManagementPage.tsx` component
**Step 3:** Create page wrapper and route
**Step 4:** Test manually in browser
**Step 5:** Commit

---

## Task 2: Maintenance Page (Gap 1.3)

**Files:**
- Create: `apps/packages/ui/src/components/Option/Admin/MaintenancePage.tsx`
- Modify: `apps/tldw-frontend/pages/admin/maintenance.tsx` (replace placeholder)
- Create: `apps/tldw-frontend/routes/option-admin-maintenance.tsx`
- Modify: `apps/packages/ui/src/services/tldw/TldwApiClient.ts`

**Backend endpoints to surface:**
- Maintenance mode: GET/PUT `/admin/maintenance`
- Rotation runs: CRUD `/admin/maintenance/rotation-runs`
- Feature flags: GET/PUT/DELETE `/admin/feature-flags`
- Incidents: CRUD `/admin/incidents`

**UI Layout:**
```
PageShell
├── Admin Guard
├── Page Title: "Maintenance & Operations"
├── Maintenance Mode Card
│   ├── Toggle switch (enable/disable)
│   ├── Message input
│   └── Allowlist (comma-separated IPs/users)
├── Feature Flags Card
│   ├── Table: Flag Key, Enabled (toggle), Description
│   └── Delete action
├── Incidents Card
│   ├── Table: Title, Status, Severity, Created
│   ├── Create incident form
│   └── Expandable: incident events timeline
└── Rotation Runs Card (collapsible)
    ├── Table: Run ID, Status, Started, Completed
    └── Create run button
```

**Step 1:** Add API client methods
**Step 2:** Create `MaintenancePage.tsx`
**Step 3:** Replace placeholder in `maintenance.tsx`
**Step 4:** Commit

---

## Task 3: Monitoring/Alerting Dashboard (Gap 1.8)

**Files:**
- Create: `apps/packages/ui/src/components/Option/Admin/MonitoringDashboardPage.tsx`
- Create: `apps/tldw-frontend/pages/admin/monitoring.tsx`
- Create: `apps/tldw-frontend/routes/option-admin-monitoring.tsx`
- Modify: `apps/packages/ui/src/services/tldw/TldwApiClient.ts`

**Backend endpoints to surface:**
- Alert rules: GET/POST/DELETE `/admin/monitoring/alert-rules`
- Alert actions: assign, snooze, escalate
- Alert history: GET `/admin/monitoring/alerts/history`
- Security alerts: GET `/admin/security/alert-status`
- System stats: GET `/admin/stats`
- Activity: GET `/admin/activity`

**UI Layout:**
```
PageShell
├── Admin Guard
├── Page Title: "Monitoring & Alerts"
├── System Overview Card
│   ├── Stats: Users, Storage, Sessions (from /admin/stats)
│   └── Security alert status badge
├── Alert Rules Card
│   ├── Table: Metric, Operator, Threshold, Duration, Severity
│   ├── Create rule form (inline)
│   └── Delete action
├── Active Alerts Card
│   ├── Table: Alert, Severity, Time, Assigned To
│   └── Actions: Assign, Snooze, Escalate
├── Alert History Card (collapsible)
│   └── Timeline/table of past alert events
└── Activity Chart (collapsible)
    └── Time-series of requests/errors (from /admin/activity)
```

**Step 1-4:** Same pattern as above

---

## Task 4: Usage Analytics Dashboard (Gap 1.7)

**Files:**
- Create: `apps/packages/ui/src/components/Option/Admin/UsageAnalyticsPage.tsx`
- Create: `apps/tldw-frontend/pages/admin/usage.tsx`
- Create: `apps/tldw-frontend/routes/option-admin-usage.tsx`
- Modify: `apps/packages/ui/src/services/tldw/TldwApiClient.ts`

**Backend endpoints to surface:**
- Daily usage: GET `/admin/usage/daily`
- Top users: GET `/admin/usage/top`
- CSV exports: GET `/admin/usage/daily/export.csv`, `/admin/usage/top/export.csv`
- LLM usage: GET `/admin/llm-usage`, `/admin/llm-usage/summary`, `/admin/llm-usage/top-spenders`
- LLM CSV: GET `/admin/llm-usage/export.csv`
- Router analytics: GET `/admin/router-analytics/status`, `/providers`, `/models`

**UI Layout:**
```
PageShell
├── Admin Guard
├── Page Title: "Usage Analytics"
├── Date Range Selector (last 7d, 30d, custom)
├── Daily Usage Card
│   ├── Summary stats: Total requests, Total bytes, Error rate
│   └── Table: Date, Requests, Bytes In/Out, Errors, Unique Users
├── Top Users Card
│   ├── Table: Username, Requests, Bytes, Errors
│   └── Export CSV button
├── LLM Usage Card
│   ├── Summary: Total tokens, Total cost, Top provider
│   ├── Table: Provider, Model, Tokens, Cost
│   ├── Top Spenders table
│   └── Export CSV button
└── Provider Analytics Card (collapsible)
    ├── Table: Provider, Success Rate, Avg Latency, Tokens
    └── Model breakdown sub-table
```

**Step 1-4:** Same pattern

---

## Task 5: Orgs/Teams Management (Gap 1.1)

**Files:**
- Create: `apps/packages/ui/src/components/Option/Admin/OrgsTeamsPage.tsx`
- Modify: `apps/tldw-frontend/pages/admin/orgs.tsx` (replace placeholder)
- Create: `apps/tldw-frontend/routes/option-admin-orgs.tsx`
- Modify: `apps/packages/ui/src/services/tldw/TldwApiClient.ts`

**Backend endpoints to surface (17):**
- Orgs: POST/GET `/admin/orgs`
- Org members: POST/GET/DELETE/PATCH `/admin/orgs/{org_id}/members`
- Teams: POST/GET `/admin/orgs/{org_id}/teams`, GET `/admin/teams/{team_id}`
- Team members: POST/GET/DELETE/PATCH `/admin/teams/{team_id}/members`
- User views: GET `/admin/users/{user_id}/org-memberships`, `/team-memberships`

**UI Layout:**
```
PageShell
├── Admin Guard
├── Page Title: "Organizations & Teams"
├── Organizations Table
│   ├── Columns: Name, Slug, Member Count, Created
│   ├── Create Org button → modal
│   └── Expandable row: Org Details
│       ├── Members Table
│       │   ├── Columns: Username, Role, Status, Joined
│       │   ├── Add Member button → modal
│       │   ├── Inline role selector
│       │   └── Remove action
│       └── Teams Sub-table
│           ├── Columns: Team Name, Member Count
│           ├── Create Team button → modal
│           └── Expandable: Team Members
└── User Membership Lookup (search user → show their orgs/teams)
```

**Step 1-4:** Same pattern

---

## Task 6: Data Ops Page (Gap 1.2)

**Files:**
- Create: `apps/packages/ui/src/components/Option/Admin/DataOpsPage.tsx`
- Modify: `apps/tldw-frontend/pages/admin/data-ops.tsx` (replace placeholder)
- Create: `apps/tldw-frontend/routes/option-admin-data-ops.tsx`
- Modify: `apps/packages/ui/src/services/tldw/TldwApiClient.ts`

**Backend endpoints to surface (24+):**
- Backups: GET/POST `/admin/backups`, POST restore
- Backup schedules: CRUD
- Backup bundles: CRUD + download
- DSR: preview, create, list, execute
- Retention policies: GET, preview, update

**UI Layout:**
```
PageShell
├── Admin Guard
├── Page Title: "Data Operations"
├── Tabs
│   ├── Tab 1: Backups
│   │   ├── Backup List Table
│   │   │   ├── Columns: Dataset, User, Created, Size, Status
│   │   │   └── Actions: Restore, Download
│   │   ├── Create Backup form
│   │   └── Backup Schedules sub-section
│   ├── Tab 2: Data Subject Requests
│   │   ├── DSR List Table
│   │   │   ├── Columns: ID, Requester, Type, Status, Created
│   │   │   └── Actions: Execute (for erasure), View details
│   │   └── Create DSR form (preview first, then record)
│   ├── Tab 3: Retention Policies
│   │   ├── Policy Table
│   │   │   ├── Columns: Policy Key, Current Days, Description
│   │   │   └── Inline edit: retention days
│   │   └── Preview impact button
│   └── Tab 4: Bundles
│       ├── Bundle List Table
│       └── Create/Import Bundle forms
```

**Step 1-4:** Same pattern

---

## Task 7: RBAC/Permissions Editor (Gap 1.6)

**Files:**
- Create: `apps/packages/ui/src/components/Option/Admin/RbacEditorPage.tsx`
- Create: `apps/tldw-frontend/pages/admin/rbac.tsx`
- Create: `apps/tldw-frontend/routes/option-admin-rbac.tsx`
- Modify: `apps/packages/ui/src/services/tldw/TldwApiClient.ts`

**Backend endpoints to surface (28):**
- Roles: CRUD
- Permissions: list, create, categories
- Role-permission: grant/revoke, matrix, matrix-boolean
- Tool permissions: CRUD, batch grant/revoke, prefix operations
- User roles: assign/remove
- User overrides: CRUD, effective permissions
- Rate limits: set/clear per role and user

**UI Layout:**
```
PageShell
├── Admin Guard
├── Page Title: "Roles & Permissions"
├── Tabs
│   ├── Tab 1: Permission Matrix
│   │   ├── Matrix grid: Roles (columns) x Permissions (rows)
│   │   ├── Checkbox cells: click to grant/revoke
│   │   └── Filter by permission category
│   ├── Tab 2: Roles
│   │   ├── Roles Table
│   │   │   ├── Columns: Name, Description, System, Permission Count
│   │   │   ├── Create Role form
│   │   │   └── Delete (non-system only)
│   │   └── Expandable: role permissions list
│   ├── Tab 3: User Permissions
│   │   ├── User search
│   │   ├── Assigned roles table (add/remove)
│   │   ├── Permission overrides table (add/remove)
│   │   └── Effective permissions (computed, read-only)
│   └── Tab 4: Tool Permissions
│       ├── Tool permissions table
│       ├── Batch grant/revoke by role
│       └── Prefix operations
```

**Step 1-4:** Same pattern

---

## Dependency Graph

```
Task 1 (API Keys, S) ─── independent
Task 2 (Maintenance, M) ── independent
Task 3 (Monitoring, M) ─── independent
Task 4 (Usage, M) ──────── independent
Task 5 (Orgs/Teams, L) ─── independent
Task 6 (Data Ops, L) ───── independent (uses DSR from Phase 1)
Task 7 (RBAC, L) ───────── independent
```

All tasks are independent and can be implemented in any order.

## Verification

For each page:
- [ ] Page loads without errors at `/admin/{page-name}`
- [ ] Admin guard works (403 shows "forbidden", 404 shows "not found")
- [ ] Data loads from backend API
- [ ] Tables render with correct columns
- [ ] CRUD operations work (create, read, update, delete)
- [ ] Error states display sanitized messages
- [ ] Loading states show spinners
