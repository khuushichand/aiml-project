# Stage 1: Dashboard & Overview — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enhance the admin dashboard with missing KPIs, richer activity charts, better alert/health visibility, auto-refresh, and accessibility fixes — addressing all 14 findings from REVIEW.md section 1.

**Architecture:** Backend adds 3 fields to `GET /admin/stats` (`SystemStatsResponse` in `admin_schemas.py`, service in `admin_system_service.py`). Service uses raw SQL with dual PostgreSQL/SQLite support. Frontend modifies 7 existing dashboard components. Activity chart gets toggleable `Line` series (requires adding `Line` import and `yAxisId` to existing `Area` series). AlertsBanner and SystemHealth types need extending to include `message` fields. Auto-refresh uses a simple `setInterval` in `useEffect`.

**Review corrections applied:**
- Backend endpoint is `/admin/stats` (not `/admin/dashboard/stats`)
- `DashboardAlertSummaryItem` has no `message` field — must extend or pass full alerts array
- `DashboardSubsystemHealth` has no `message` field — must extend type and populate from health responses
- ActivitySection chart needs `Line` import added and `yAxisId="left"` on existing Area series
- QuickActionsCard uses hardcoded JSX — add tiles inline
- `formatTimeAgo` is local to page.tsx — pass as prop to DashboardHeader

**Tech Stack:** FastAPI (Python), Next.js 15 / React 19 / TypeScript, Recharts, Radix UI, Tailwind CSS 4, Vitest

**Repos:**
- Backend: `./tldw_Server_API/`
- Frontend: `./admin-ui/`

---

## Task 1: Backend — Add active sessions, tokens today, MCP invocations to dashboard stats

**Findings:** 1.1, 1.2, 1.4

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/admin/` — find the dashboard stats endpoint
- Modify: the corresponding service/schema files

**Step 1: Find the dashboard stats endpoint**

Search the backend for the dashboard stats route:
```bash
grep -rn "dashboard" tldw_Server_API/app/api/v1/endpoints/admin/ --include="*.py" | grep -i "stats\|dashboard"
```
Also check `lib/api-client.ts` line 275 for `getDashboardStats` to find the URL path.

**Step 2: Add fields to the response**

Add to the dashboard stats response (Pydantic model or dict):
```python
active_sessions_count: int | None = None    # from ACP sessions with status='active'
tokens_today: dict | None = None            # { prompt: int, completion: int, total: int, trend_direction: str }
mcp_invocations_today: int | None = None    # from MCP metrics if available, else null
```

**Step 3: Populate active_sessions_count**

In the stats handler or service, query the ACP sessions store:
```python
store = await get_acp_session_store()
active_sessions = await store.list_sessions(status="active", limit=0, offset=0)
# active_sessions returns (records, total) — use total
stats["active_sessions_count"] = active_sessions[1] if active_sessions else 0
```

**Step 4: Populate tokens_today**

Query LLM usage for today:
```python
from datetime import date
today = date.today().isoformat()
# Use existing usage aggregation — check admin_usage.py for the pattern
# Aggregate prompt_tokens, completion_tokens from llm_usage for today
stats["tokens_today"] = {
    "prompt": prompt_total,
    "completion": completion_total,
    "total": prompt_total + completion_total,
}
```

**Step 5: Populate mcp_invocations_today**

Check if MCP metrics are available:
```python
try:
    mcp_metrics = await get_mcp_metrics()  # check if this exists
    stats["mcp_invocations_today"] = mcp_metrics.get("total_calls_today")
except Exception:
    stats["mcp_invocations_today"] = None  # gracefully null if not instrumented
```

**Step 6: Commit**

```bash
git commit -m "feat(backend): add active sessions, tokens, and MCP invocations to dashboard stats"
```

---

## Task 2: Frontend — Add Active Sessions and Tokens Today KPI cards (1.1, 1.2)

**Files:**
- Modify: `admin-ui/components/dashboard/StatsGrid.tsx:22-27` (props), `:142-279` (cards)
- Modify: `admin-ui/app/page.tsx:155-166` (DashboardUIStats type)

**Step 1: Extend DashboardUIStats in page.tsx**

Find the `DashboardUIStats` type/interface (around line 155-166) and add:
```typescript
activeSessionsCount: number | null;
tokensToday: { prompt: number; completion: number; total: number } | null;
mcpInvocationsToday: number | null;
```

Initialize these in the state default. In `loadDashboardData`, extract from the dashboard stats response:
```typescript
activeSessionsCount: dashboardStats?.active_sessions_count ?? null,
tokensToday: dashboardStats?.tokens_today ?? null,
mcpInvocationsToday: dashboardStats?.mcp_invocations_today ?? null,
```

**Step 2: Add Active Sessions card to StatsGrid**

After the "Jobs & Queue" card (line ~279 in StatsGrid.tsx), add:
```tsx
<Card>
  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
    <CardTitle className="text-sm font-medium">Active Sessions</CardTitle>
    <Users className="h-4 w-4 text-muted-foreground" />
  </CardHeader>
  <CardContent>
    <div className="text-2xl font-bold">
      {stats.activeSessionsCount ?? '—'}
    </div>
    <p className="text-xs text-muted-foreground">ACP sessions currently active</p>
  </CardContent>
</Card>
```

**Step 3: Add Tokens Today card**

```tsx
<Card>
  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
    <CardTitle className="text-sm font-medium">Tokens Today</CardTitle>
    <Zap className="h-4 w-4 text-muted-foreground" />
  </CardHeader>
  <CardContent>
    <div className="text-2xl font-bold">
      {stats.tokensToday ? formatCompactNumber(stats.tokensToday.total) : '—'}
    </div>
    {stats.tokensToday && (
      <p className="text-xs text-muted-foreground">
        {formatCompactNumber(stats.tokensToday.prompt)} prompt · {formatCompactNumber(stats.tokensToday.completion)} completion
      </p>
    )}
  </CardContent>
</Card>
```

Add a `formatCompactNumber` helper:
```typescript
function formatCompactNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}
```

**Step 4: Conditionally add MCP Calls card (1.4)**

Only render when data is available:
```tsx
{stats.mcpInvocationsToday != null && (
  <Card>
    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
      <CardTitle className="text-sm font-medium">MCP Calls</CardTitle>
      <Terminal className="h-4 w-4 text-muted-foreground" />
    </CardHeader>
    <CardContent>
      <div className="text-2xl font-bold">{formatCompactNumber(stats.mcpInvocationsToday)}</div>
      <p className="text-xs text-muted-foreground">Tool invocations today</p>
    </CardContent>
  </Card>
)}
```

**Step 5: Run typecheck**

Run: `cd admin-ui && ./node_modules/.bin/tsc --noEmit`
Expected: 0 errors

**Step 6: Commit**

```bash
git commit -m "feat(admin-ui): add Active Sessions, Tokens Today, and MCP Calls KPI cards

Extends StatsGrid with 2 new cards (Active Sessions, Tokens Today)
and conditionally renders MCP Calls when data is available."
```

---

## Task 3: Frontend — Add error/latency/cost overlays to activity chart (1.5, 1.6)

**Files:**
- Modify: `admin-ui/lib/dashboard-activity.ts:21-26` (DashboardActivityChartPoint type)
- Modify: `admin-ui/components/dashboard/ActivitySection.tsx:34-38` (local type), `:147-164` (chart series)
- Modify: `admin-ui/app/page.tsx` (pass additional data)

**Step 1: Extend the activity chart point type**

In `lib/dashboard-activity.ts`, add to `DashboardActivityChartPoint` (line 21-26):
```typescript
export interface DashboardActivityChartPoint {
  bucketStart: string;
  name: string;
  requests: number;
  users: number;
  errors?: number;
  latencyP95Ms?: number;
  costUsd?: number;
}
```

**Step 2: Update ActivitySection chart type and add toggle state**

In `ActivitySection.tsx`, update the local `ActivityChartPoint` type to match (line 34-38). Add state for series visibility:
```typescript
const [visibleSeries, setVisibleSeries] = useState<Record<string, boolean>>({
  requests: true,
  users: true,
  errors: false,
  latencyP95Ms: false,
  costUsd: false,
});
```

**Step 3: Add toggle buttons for additional series**

After the range toggle buttons (line ~130), add optional series toggles:
```tsx
<div className="flex gap-1">
  {['errors', 'latencyP95Ms', 'costUsd'].map((key) => {
    const hasData = activityChartData.some((d: Record<string, unknown>) => d[key] != null && d[key] !== 0);
    if (!hasData) return null;
    const labels: Record<string, string> = { errors: 'Errors', latencyP95Ms: 'Latency', costUsd: 'Cost' };
    return (
      <Button
        key={key}
        variant={visibleSeries[key] ? 'default' : 'outline'}
        size="sm"
        onClick={() => setVisibleSeries(prev => ({ ...prev, [key]: !prev[key] }))}
      >
        {labels[key]}
      </Button>
    );
  })}
</div>
```

**Step 4: Add Line series to the chart**

After existing Area series (line ~164), add conditional Line series:
```tsx
{visibleSeries.errors && (
  <Line type="monotone" dataKey="errors" stroke="#ef4444" strokeWidth={2}
    dot={false} yAxisId="left" name="Errors" />
)}
{visibleSeries.latencyP95Ms && (
  <Line type="monotone" dataKey="latencyP95Ms" stroke="#f59e0b" strokeWidth={2}
    dot={false} yAxisId="right" name="Latency (ms)" />
)}
{visibleSeries.costUsd && (
  <Line type="monotone" dataKey="costUsd" stroke="#8b5cf6" strokeWidth={2}
    strokeDasharray="5 5" dot={false} yAxisId="right" name="Cost ($)" />
)}
```

Add a right Y-axis if any overlay is visible:
```tsx
{(visibleSeries.latencyP95Ms || visibleSeries.costUsd) && (
  <YAxis yAxisId="right" orientation="right" />
)}
```

Import `Line, YAxis` from recharts if not already imported.

**Step 5: Commit**

```bash
git commit -m "feat(admin-ui): add toggleable error, latency, and cost overlays to activity chart

Activity chart now supports optional error count, p95 latency,
and cost series as toggleable Line overlays with dual Y-axis."
```

---

## Task 4: Frontend — Add Job Queue to System Health grid (1.7)

**Files:**
- Modify: `admin-ui/lib/dashboard-health.ts:3-12` (DASHBOARD_SUBSYSTEMS)
- Modify: `admin-ui/app/page.tsx` (pass job health data)

**Step 1: Add job_queue subsystem**

In `dashboard-health.ts`, add to DASHBOARD_SUBSYSTEMS (after line 11):
```typescript
{ key: 'job_queue', label: 'Job Queue' },
```

**Step 2: Wire job queue health from page.tsx**

In the `buildDashboardSystemHealth()` call in page.tsx, add a job queue health entry. Source from `jobsStats` (which is already fetched at line 286). The health status should be:
- healthy: if failedJobs === 0 and queueDepth < some threshold
- degraded: if failedJobs > 0 or queueDepth is high
- down: if jobsStats fetch failed

**Step 3: Commit**

```bash
git commit -m "feat(admin-ui): add Job Queue to system health grid"
```

---

## Task 5: Frontend — Show error detail for degraded/down subsystems (1.8)

**Files:**
- Modify: `admin-ui/components/dashboard/ActivitySection.tsx:182-204` (health grid rendering)

**Step 1: Add error detail display**

In the health grid mapping (line ~182-204), after the status badge, add:
```tsx
{subsystemHealth.status !== 'healthy' && subsystemHealth.message && (
  <p className="text-xs text-muted-foreground mt-1 truncate max-w-[200px]" title={subsystemHealth.message}>
    {subsystemHealth.message}
  </p>
)}
```

This requires ensuring `DashboardSubsystemHealth` type includes a `message` field. Check the type in `dashboard-health.ts` and add it if missing.

**Step 2: Commit**

```bash
git commit -m "feat(admin-ui): show error detail for degraded/down health subsystems"
```

---

## Task 6: Frontend — Add severity filter to RecentActivityCard (1.9)

**Files:**
- Modify: `admin-ui/components/dashboard/RecentActivityCard.tsx`

**Step 1: Add filter state and toggle buttons**

Add a severity filter state:
```typescript
const [severityFilter, setSeverityFilter] = useState<string>('all');
```

In the card header (before the loading check), add toggle buttons:
```tsx
<div className="flex gap-1">
  {['all', 'critical', 'warning', 'info'].map((level) => (
    <Button
      key={level}
      variant={severityFilter === level ? 'default' : 'outline'}
      size="sm"
      onClick={() => setSeverityFilter(level)}
    >
      {level === 'all' ? 'All' : level.charAt(0).toUpperCase() + level.slice(1)}
      {level !== 'all' && (
        <Badge variant="secondary" className="ml-1">
          {activityWithMetadata.filter(a => a.severity === level).length}
        </Badge>
      )}
    </Button>
  ))}
</div>
```

**Step 2: Apply the filter**

Filter the displayed entries:
```typescript
const filteredActivity = severityFilter === 'all'
  ? activityWithMetadata
  : activityWithMetadata.filter(a => a.severity === severityFilter);
```

Use `filteredActivity` instead of `activityWithMetadata` in the rendering map.

**Step 3: Commit**

```bash
git commit -m "feat(admin-ui): add severity filter to RecentActivityCard

Toggle buttons for All/Critical/Warning/Info with count badges.
Filters displayed audit entries by severity level."
```

---

## Task 7: Frontend — Enhance AlertsBanner with alert summaries (1.10)

**Files:**
- Modify: `admin-ui/components/dashboard/AlertsBanner.tsx`
- Modify: `admin-ui/app/page.tsx` (pass full alert data, not just summary)

**Step 1: Pass full alert data to banner**

In page.tsx, the banner currently receives `DashboardAlertSummaryItem[]`. Update it to also receive the most recent alert message. Either:
- Add a `topAlertMessage` prop to AlertsBanner
- Or pass the full `alerts` array and let the banner extract the message

**Step 2: Display the top alert message**

In AlertsBanner, after the severity count badges, add:
```tsx
{topAlert && (
  <span className="text-sm truncate max-w-md">
    — {topAlert.message}
  </span>
)}
```

Where `topAlert` is the highest-severity most recent alert.

**Step 3: Commit**

```bash
git commit -m "feat(admin-ui): show top alert message in AlertsBanner"
```

---

## Task 8: Frontend — Add quick-acknowledge button to AlertsBanner (1.11)

**Files:**
- Modify: `admin-ui/components/dashboard/AlertsBanner.tsx`

**Step 1: Add acknowledge handler**

Add a handler that acknowledges all critical alerts:
```typescript
const handleAcknowledgeAll = async () => {
  try {
    const criticalAlerts = alerts.filter(a => a.severity === 'critical' && !a.acknowledged);
    await Promise.all(criticalAlerts.map(a => api.acknowledgeAlert(a.id)));
    onRefresh?.(); // trigger dashboard reload
  } catch {
    // silent fail — user can use monitoring page
  }
};
```

**Step 2: Add the button**

After the "View all" link, add:
```tsx
{criticalCount > 0 && (
  <Button variant="ghost" size="sm" onClick={handleAcknowledgeAll}>
    Acknowledge All
  </Button>
)}
```

Props will need `onRefresh` callback added.

**Step 3: Commit**

```bash
git commit -m "feat(admin-ui): add Acknowledge All button to AlertsBanner"
```

---

## Task 9: Frontend — Add Monitoring to QuickActionsCard (1.12)

**Files:**
- Modify: `admin-ui/components/dashboard/QuickActionsCard.tsx:15-74`

**Step 1: Add Monitoring tile**

Add after the Configuration tile (line ~74):
```tsx
{
  label: 'Monitoring',
  href: '/monitoring',
  icon: Activity,
  description: 'System health & alerts',
}
```

Import `Activity` from lucide-react.

Optionally, also add a conditional Billing tile:
```tsx
{isBillingEnabled() && {
  label: 'Billing',
  href: '/plans',
  icon: CreditCard,
  description: 'Plans & subscriptions',
}}
```

**Step 2: Commit**

```bash
git commit -m "feat(admin-ui): add Monitoring tile to QuickActionsCard"
```

---

## Task 10: Frontend — Add dashboard auto-refresh (1.13)

**Files:**
- Modify: `admin-ui/app/page.tsx`
- Modify: `admin-ui/components/dashboard/DashboardHeader.tsx`

**Step 1: Add auto-refresh hook to page.tsx**

Create a simple useInterval utility (or inline):
```typescript
const [autoRefreshEnabled, setAutoRefreshEnabled] = useState(true);
const AUTO_REFRESH_INTERVAL_MS = 60_000; // 60 seconds

useEffect(() => {
  if (!autoRefreshEnabled) return;
  const id = setInterval(() => {
    loadDashboardData();
  }, AUTO_REFRESH_INTERVAL_MS);
  return () => clearInterval(id);
}, [autoRefreshEnabled, loadDashboardData]);
```

Track last refresh time:
```typescript
const [lastRefreshedAt, setLastRefreshedAt] = useState<Date | null>(null);
```
Update it at the end of `loadDashboardData`:
```typescript
setLastRefreshedAt(new Date());
```

**Step 2: Update DashboardHeader to show auto-refresh status**

Add props to DashboardHeader:
```typescript
autoRefreshEnabled: boolean;
onToggleAutoRefresh: () => void;
lastRefreshedAt: Date | null;
```

Display in the header:
```tsx
<div className="flex items-center gap-2 text-xs text-muted-foreground">
  {lastRefreshedAt && (
    <span>Updated {formatTimeAgo(lastRefreshedAt)}</span>
  )}
  <Button
    variant="ghost"
    size="sm"
    onClick={onToggleAutoRefresh}
    className="text-xs"
  >
    Auto-refresh: {autoRefreshEnabled ? 'ON' : 'OFF'}
  </Button>
</div>
```

**Step 3: Commit**

```bash
git commit -m "feat(admin-ui): add 60-second auto-refresh to dashboard

Dashboard now auto-refreshes every 60 seconds with a toggle
to pause/resume. Shows 'Updated X ago' in header."
```

---

## Task 11: Frontend — Fix storage progress bar ARIA (1.14)

**Files:**
- Modify: `admin-ui/components/dashboard/StatsGrid.tsx:190-203`

**Step 1: Add ARIA attributes**

Find the storage progress bar div (around line 190-203). It should be a div with inline `width` styling. Add:
```tsx
<div
  role="progressbar"
  aria-valuenow={storagePercentage}
  aria-valuemin={0}
  aria-valuemax={100}
  aria-label={`Storage usage: ${storagePercentage}%`}
  className="h-2 w-full rounded-full bg-muted overflow-hidden"
>
  <div
    className={`h-full rounded-full ${storageBarColor}`}
    style={{ width: `${storagePercentage}%` }}
  />
</div>
```

**Step 2: Commit**

```bash
git commit -m "a11y(admin-ui): add ARIA attributes to storage progress bar"
```

---

## Task 12: Final verification

**Step 1: Run typecheck**

Run: `cd admin-ui && ./node_modules/.bin/tsc --noEmit`
Expected: 0 errors

**Step 2: Run tests**

Run: `cd admin-ui && bun run test`
Expected: All pass

**Step 3: Verify git log**

Run: `git log --oneline -15`
Expected: ~11 commits for Stage 1
