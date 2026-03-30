# Stage 0: Critical Safety Fixes & Quick Wins — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 3 critical safety issues, apply privileged action dialog to highest-risk operations, and ship 5 quick wins across the admin-ui.

**Architecture:** Backend changes use FastAPI with the existing service layer pattern (routes → services → SQLite/DB). Frontend changes are React component modifications using existing patterns (Vitest + Testing Library for tests). ACP data lives in SQLite via `ACPSessionStore`. Billing uses `subscription_service`.

**Tech Stack:** FastAPI (Python), Next.js 15 / React 19 / TypeScript, Vitest, Testing Library, Radix UI, Tailwind CSS 4

**Repos:**
- Backend: `/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/`
- Frontend: `/Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui/`

---

## Task 1: ACP Agent Usage Metrics — Backend Endpoint

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/agent_client_protocol.py`
- Modify: `tldw_Server_API/app/services/admin_acp_sessions_service.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/admin/admin_acp_agents.py`

**Step 1: Add Pydantic response schema**

Add to `tldw_Server_API/app/api/v1/schemas/agent_client_protocol.py` after `ACPTokenUsage` (after line 380):

```python
class ACPAgentUsageItem(BaseModel):
    agent_type: str
    invocation_count: int = 0
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    error_count: int = 0
    estimated_cost_usd: float = 0.0
    avg_tokens_per_session: float = 0.0

class ACPAgentUsageResponse(BaseModel):
    agents: list[ACPAgentUsageItem]
    range_days: int
```

**Step 2: Add service method to ACPSessionStore**

Add to `tldw_Server_API/app/services/admin_acp_sessions_service.py` on the `ACPSessionStore` class:

```python
async def get_agent_usage_stats(self, range_days: int = 7) -> list[dict]:
    """Aggregate token usage per agent_type from sessions table."""
    cutoff = (datetime.utcnow() - timedelta(days=range_days)).isoformat()
    query = """
        SELECT
            agent_type,
            COUNT(*) as invocation_count,
            COALESCE(SUM(total_tokens), 0) as total_tokens,
            COALESCE(SUM(prompt_tokens), 0) as prompt_tokens,
            COALESCE(SUM(completion_tokens), 0) as completion_tokens,
            CASE WHEN COUNT(*) > 0
                THEN CAST(COALESCE(SUM(total_tokens), 0) AS REAL) / COUNT(*)
                ELSE 0
            END as avg_tokens_per_session
        FROM sessions
        WHERE created_at >= ?
        GROUP BY agent_type
        ORDER BY total_tokens DESC
    """
    rows = await self._db.execute_query(query, (cutoff,))
    return [dict(r) for r in rows]
```

**Step 3: Add route handler**

Add to `tldw_Server_API/app/api/v1/endpoints/admin/admin_acp_agents.py`:

```python
from ..schemas.agent_client_protocol import ACPAgentUsageResponse, ACPAgentUsageItem

@router.get("/acp/agents/usage", response_model=ACPAgentUsageResponse)
async def admin_get_agent_usage(
    range_days: int = Query(7, ge=1, le=90),
    principal: AuthPrincipal = Depends(get_auth_principal),
) -> ACPAgentUsageResponse:
    store = await get_acp_session_store()
    rows = await store.get_agent_usage_stats(range_days=range_days)
    return ACPAgentUsageResponse(
        agents=[ACPAgentUsageItem(**r) for r in rows],
        range_days=range_days,
    )
```

**Step 4: Run backend tests**

Run: `cd /Users/macbook-dev/Documents/GitHub/tldw_server2 && python -m pytest tests/ -k "acp" -v --timeout=30`
Expected: Existing tests pass. New endpoint tested manually or via integration test.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/agent_client_protocol.py \
       tldw_Server_API/app/services/admin_acp_sessions_service.py \
       tldw_Server_API/app/api/v1/endpoints/admin/admin_acp_agents.py
git commit -m "feat(backend): add ACP agent usage stats endpoint

Aggregates per-agent token usage from sessions table.
GET /admin/acp/agents/usage?range_days=7"
```

---

## Task 2: ACP Agent Usage Metrics — Frontend

**Files:**
- Modify: `admin-ui/lib/api-client.ts`
- Modify: `admin-ui/app/acp-agents/page.tsx`
- Modify: `admin-ui/app/acp-agents/__tests__/page.test.tsx`

**Step 1: Add API client method**

Add to `admin-ui/lib/api-client.ts` near other ACP methods:

```typescript
getACPAgentUsage: (rangeDays = 7) =>
  requestJson<{
    agents: Array<{
      agent_type: string;
      invocation_count: number;
      total_tokens: number;
      estimated_cost_usd: number;
      error_count: number;
      avg_tokens_per_session: number;
    }>;
    range_days: number;
  }>(`/acp/agents/usage?range_days=${rangeDays}`),
```

**Step 2: Write the failing test**

Add to `admin-ui/app/acp-agents/__tests__/page.test.tsx`:

```typescript
it('displays usage metrics columns when usage data is available', async () => {
  apiMock.getACPAgentConfigs.mockResolvedValue({
    agents: [
      { id: 1, type: 'code', name: 'Code Agent', description: '', system_prompt: null,
        allowed_tools: null, denied_tools: null, parameters: {}, requires_api_key: null,
        org_id: null, team_id: null, enabled: true, is_configured: true,
        created_at: '2026-01-01', updated_at: null },
    ],
    total: 1,
  });
  apiMock.getACPAgentUsage.mockResolvedValue({
    agents: [{ agent_type: 'code', invocation_count: 42, total_tokens: 150000,
               estimated_cost_usd: 1.25, error_count: 3, avg_tokens_per_session: 3571 }],
    range_days: 7,
  });
  apiMock.getACPPermissionPolicies.mockResolvedValue({ policies: [], total: 0 });

  render(<ACPAgentsPage />);

  await waitFor(() => {
    expect(screen.getByText('42')).toBeInTheDocument();
  });
  expect(screen.getByText('150K')).toBeInTheDocument();
});
```

**Step 3: Run test to verify it fails**

Run: `cd /Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui && bun run vitest run app/acp-agents/__tests__/page.test.tsx -t "displays usage metrics"`
Expected: FAIL — `getACPAgentUsage` not mocked / usage columns don't exist yet.

**Step 4: Implement the frontend changes**

In `admin-ui/app/acp-agents/page.tsx`:

a) Add usage state and fetch (after line 80, near other state):

```typescript
const [agentUsage, setAgentUsage] = useState<Record<string, {
  invocation_count: number; total_tokens: number;
  estimated_cost_usd: number; error_count: number;
}>>({});
```

b) Add usage fetch in the existing `loadAgents` callback (or alongside it):

```typescript
useEffect(() => {
  api.getACPAgentUsage(7).then((res) => {
    const map: typeof agentUsage = {};
    for (const a of res.agents) map[a.agent_type] = a;
    setAgentUsage(map);
  }).catch(() => {/* usage is optional — don't block page */});
}, []);
```

c) Add columns to table header (after "Tools" at line 333, before "Actions" at line 334):

```tsx
<TableHead>Invocations</TableHead>
<TableHead>Tokens</TableHead>
<TableHead>Cost</TableHead>
```

d) Add cells to table body (after tools cell at line 367, before actions at line 368):

```tsx
<TableCell className="text-right font-mono text-sm">
  {agentUsage[config.type]?.invocation_count ?? '—'}
</TableCell>
<TableCell className="text-right font-mono text-sm">
  {agentUsage[config.type] ? formatTokens(agentUsage[config.type].total_tokens) : '—'}
</TableCell>
<TableCell className="text-right font-mono text-sm">
  {agentUsage[config.type]?.estimated_cost_usd != null
    ? `$${agentUsage[config.type].estimated_cost_usd.toFixed(2)}`
    : '—'}
</TableCell>
```

Add a `formatTokens` helper at the top of the file:

```typescript
function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${Math.round(n / 1_000)}K`;
  return String(n);
}
```

**Step 5: Run test to verify it passes**

Run: `cd /Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui && bun run vitest run app/acp-agents/__tests__/page.test.tsx -t "displays usage metrics"`
Expected: PASS

**Step 6: Run all acp-agents tests**

Run: `cd /Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui && bun run vitest run app/acp-agents/`
Expected: All pass. Fix any regressions from column count changes.

**Step 7: Commit**

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui
git add lib/api-client.ts app/acp-agents/page.tsx app/acp-agents/__tests__/page.test.tsx
git commit -m "feat(admin-ui): display ACP agent usage metrics in agents table

Shows invocations, tokens, and cost columns fetched from new
/admin/acp/agents/usage endpoint. Gracefully shows '—' if
usage data is unavailable."
```

---

## Task 3: ACP Session Token Budgets — Backend

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/ACP_Sessions_DB.py`
- Modify: `tldw_Server_API/app/services/admin_acp_sessions_service.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/agent_client_protocol.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/admin/admin_acp_agents.py`

**Step 1: Add max_token_budget to AgentConfig dataclass**

In `tldw_Server_API/app/services/admin_acp_sessions_service.py`, add to the `AgentConfig` dataclass:

```python
max_token_budget: int | None = None  # null = unlimited
```

Also update `to_dict()` to include it, and update `from_dict()` (or `__init__`) to parse it.

**Step 2: Add max_token_budget to Pydantic schemas**

In `tldw_Server_API/app/api/v1/schemas/agent_client_protocol.py`:

Add to `ACPAgentConfigCreate` (line ~484-499):
```python
max_token_budget: int | None = None
```

Add to `ACPAgentConfigResponse` (line ~502-507):
```python
max_token_budget: int | None = None
```

**Step 3: Update create/update agent config service methods**

In the `ACPSessionStore` class, ensure `create_agent_config` and `update_agent_config` accept and persist `max_token_budget`.

**Step 4: Add budget_exceeded status handling**

In the session handler middleware (where tokens are accumulated after an LLM call), add a check:

```python
# After accumulating tokens in a session
agent_config = await store.get_agent_config_by_type(session.agent_type)
if agent_config and agent_config.max_token_budget:
    if session.total_tokens >= agent_config.max_token_budget:
        await store.close_session(session.session_id, reason="budget_exceeded")
```

Note: The exact placement depends on the ACP session execution flow. Find where `prompt_tokens`/`completion_tokens` are updated and add the check there.

**Step 5: Run backend tests**

Run: `cd /Users/macbook-dev/Documents/GitHub/tldw_server2 && python -m pytest tests/ -k "acp" -v --timeout=30`
Expected: PASS

**Step 6: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/ACP_Sessions_DB.py \
       tldw_Server_API/app/services/admin_acp_sessions_service.py \
       tldw_Server_API/app/api/v1/schemas/agent_client_protocol.py \
       tldw_Server_API/app/api/v1/endpoints/admin/admin_acp_agents.py
git commit -m "feat(backend): add token budget to ACP agent configs

Adds max_token_budget field to agent configs. Sessions are
auto-terminated when cumulative tokens exceed the budget."
```

---

## Task 4: ACP Session Token Budgets — Frontend

**Files:**
- Modify: `admin-ui/app/acp-agents/page.tsx`
- Modify: `admin-ui/app/acp-sessions/page.tsx`
- Modify: `admin-ui/app/acp-sessions/__tests__/page.test.tsx`

**Step 1: Write the failing test for budget progress bar**

Add to `admin-ui/app/acp-sessions/__tests__/page.test.tsx`:

```typescript
it('shows budget progress bar when agent has token budget', async () => {
  apiMock.getACPSessions.mockResolvedValue({
    sessions: [{
      session_id: 'sess-1', user_id: 1, agent_type: 'code', name: 'Test',
      status: 'active', created_at: '2026-01-01', last_activity_at: '2026-01-01',
      message_count: 5, usage: { prompt_tokens: 500, completion_tokens: 300, total_tokens: 800 },
      tags: [], has_websocket: false,
      agent_budget: 1000,
    }],
    total: 1,
  });

  render(<ACPSessionsPage />);

  await waitFor(() => {
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });
  expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '80');
});
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui && bun run vitest run app/acp-sessions/__tests__/page.test.tsx -t "budget progress"`
Expected: FAIL

**Step 3: Add budget field to agent form**

In `admin-ui/app/acp-agents/page.tsx`, add to `defaultAgentForm` (after line 64):

```typescript
max_token_budget: '',
```

Add form field in the create/edit dialog (after max_tokens at line 514):

```tsx
<FormInput
  label="Session Token Budget"
  type="number"
  placeholder="Leave empty for unlimited"
  value={agentForm.max_token_budget}
  onChange={(e) => setAgentForm({ ...agentForm, max_token_budget: e.target.value })}
  description="Maximum total tokens per session. Sessions are auto-terminated when exceeded."
/>
```

Update the submit handler to include `max_token_budget: agentForm.max_token_budget ? parseInt(agentForm.max_token_budget) : null`.

**Step 4: Add budget display to sessions table**

In `admin-ui/app/acp-sessions/page.tsx`:

a) Extend the `ACPSession` interface (line 21-37) with:

```typescript
agent_budget?: number | null;
```

b) Replace the plain token display (lines 235-239) with:

```tsx
<TableCell>
  {session.agent_budget ? (
    <div className="flex flex-col gap-1">
      <span className="text-xs font-mono">
        {formatTokens(session.usage.total_tokens)} / {formatTokens(session.agent_budget)}
      </span>
      <div
        role="progressbar"
        aria-valuenow={Math.round((session.usage.total_tokens / session.agent_budget) * 100)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Token budget usage"
        className="h-1.5 w-full rounded-full bg-muted overflow-hidden"
      >
        <div
          className={`h-full rounded-full transition-all ${
            session.usage.total_tokens / session.agent_budget > 0.9 ? 'bg-red-500' :
            session.usage.total_tokens / session.agent_budget > 0.7 ? 'bg-yellow-500' :
            'bg-green-500'
          }`}
          style={{ width: `${Math.min(100, (session.usage.total_tokens / session.agent_budget) * 100)}%` }}
        />
      </div>
    </div>
  ) : (
    <span className="text-xs font-mono" title={`Prompt: ${session.usage.prompt_tokens} | Completion: ${session.usage.completion_tokens}`}>
      {formatTokens(session.usage.total_tokens)}
    </span>
  )}
</TableCell>
```

Add `budget_exceeded` badge in the status cell:

```tsx
{session.status === 'budget_exceeded' && (
  <Badge variant="destructive">Budget Exceeded</Badge>
)}
```

**Step 5: Run test to verify it passes**

Run: `cd /Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui && bun run vitest run app/acp-sessions/__tests__/page.test.tsx -t "budget progress"`
Expected: PASS

**Step 6: Run all session and agent tests**

Run: `cd /Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui && bun run vitest run app/acp-sessions/ app/acp-agents/`
Expected: All PASS

**Step 7: Commit**

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui
git add app/acp-agents/page.tsx app/acp-sessions/page.tsx app/acp-sessions/__tests__/page.test.tsx
git commit -m "feat(admin-ui): add token budget to agent config and session progress bar

Agent form now has optional token budget field. Sessions table
shows progress bar with green/yellow/red thresholds (70%/90%)
when a budget is set. Supports budget_exceeded status badge."
```

---

## Task 5: Plan Deletion Subscriber Check

**Files:**
- Modify: `admin-ui/app/plans/page.tsx`
- Modify: `admin-ui/app/plans/__tests__/page.test.tsx`

**Step 1: Write the failing test**

Add to `admin-ui/app/plans/__tests__/page.test.tsx`:

```typescript
it('blocks plan deletion when active subscribers exist', async () => {
  apiMock.getPlans.mockResolvedValue([
    { id: '1', name: 'Pro', tier: 'pro', stripe_product_id: null, stripe_price_id: null,
      monthly_price_cents: 2900, included_token_credits: 100000, overage_rate: '0.50',
      features: [], is_default: false },
  ]);
  apiMock.getSubscriptions.mockResolvedValue([
    { id: 's1', org_id: 'org1', plan_id: '1', plan: null, stripe_subscription_id: null,
      status: 'active', current_period_start: '', current_period_end: '',
      trial_end: null, cancel_at: null, created_at: '', updated_at: '' },
  ]);

  const user = userEvent.setup();
  render(<PlansPage />);

  await screen.findByText('Pro');
  await user.click(screen.getByRole('button', { name: /Delete/ }));

  await waitFor(() => {
    expect(screen.getByText(/1 active subscription/i)).toBeInTheDocument();
  });
  // Delete button should be disabled in the confirmation dialog
  expect(confirmMock).not.toHaveBeenCalled();
});
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui && bun run vitest run app/plans/__tests__/page.test.tsx -t "blocks plan deletion"`
Expected: FAIL — no subscriber check exists yet.

**Step 3: Implement the subscriber check**

In `admin-ui/app/plans/page.tsx`, replace `handleDelete` (lines 149-167) with:

```typescript
const handleDelete = async (plan: Plan) => {
  // Check for active subscribers before allowing deletion
  try {
    const subs = await api.getSubscriptions({ plan_id: plan.id });
    const activeSubs = subs.filter(
      (s) => s.status !== 'canceled'
    );

    if (activeSubs.length > 0) {
      toast.error(
        `Cannot delete "${plan.name}" — ${activeSubs.length} active subscription${activeSubs.length === 1 ? '' : 's'}. Migrate subscribers to another plan first.`
      );
      return;
    }
  } catch {
    // If we can't check subscribers, block deletion to be safe
    toast.error('Unable to verify subscriber count. Please try again.');
    return;
  }

  const confirmed = await confirm({
    title: 'Delete Plan',
    message: `Are you sure you want to delete the plan "${plan.name}"? This action cannot be undone.`,
    confirmText: 'Delete',
    variant: 'danger',
    icon: 'delete',
  });
  if (!confirmed) return;

  try {
    await api.deletePlan(plan.id);
    success('Plan Deleted', `Plan "${plan.name}" has been deleted`);
    loadPlans();
  } catch (err: unknown) {
    console.error('Failed to delete plan:', err);
    showError('Failed to delete plan', err instanceof Error ? err.message : 'Please try again.');
  }
};
```

Ensure `toast` is available — it should already be imported from `useToast()`.

**Step 4: Run test to verify it passes**

Run: `cd /Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui && bun run vitest run app/plans/__tests__/page.test.tsx -t "blocks plan deletion"`
Expected: PASS

**Step 5: Run all plans tests**

Run: `cd /Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui && bun run vitest run app/plans/`
Expected: All PASS

**Step 6: Commit**

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui
git add app/plans/page.tsx app/plans/__tests__/page.test.tsx
git commit -m "fix(admin-ui): block plan deletion when active subscribers exist

Fetches subscriptions for the plan before allowing deletion.
Shows error toast with subscriber count if any non-canceled
subscriptions exist."
```

---

## Task 6: PrivilegedActionDialog — Tier 1 Conversions

**Files:**
- Modify: `admin-ui/app/plans/page.tsx`
- Modify: `admin-ui/app/organizations/page.tsx`
- Modify: `admin-ui/app/byok/page.tsx`
- Modify: `admin-ui/app/subscriptions/page.tsx`
- Modify: `admin-ui/app/resource-governor/page.tsx`

**Step 1: Understand the conversion pattern**

Each conversion follows this template. Original:

```typescript
const confirmed = await confirm({ title, message, variant: 'danger', ... });
if (!confirmed) return;
await api.doThing(id);
```

Converted:

```typescript
const result = await privilegedAction.prompt({
  title,
  message,
  icon: 'delete',
  requirePassword: true,
});
if (!result) return;
// result.reason is the audit reason (min 8 chars)
// result.adminPassword is the re-auth password
await api.doThing(id);
```

**Step 2: Convert plans/page.tsx (already modified in Task 5)**

In `admin-ui/app/plans/page.tsx`:

a) Add import:
```typescript
import { usePrivilegedActionDialog } from '@/components/ui/privileged-action-dialog';
```

b) Add hook:
```typescript
const privilegedAction = usePrivilegedActionDialog();
```

c) Replace the `confirm()` call in `handleDelete` (the one remaining after subscriber check) with:

```typescript
const result = await privilegedAction.prompt({
  title: 'Delete Plan',
  message: `Are you sure you want to delete the plan "${plan.name}"? This action cannot be undone.`,
  icon: 'delete',
  requirePassword: true,
});
if (!result) return;
```

**Step 3: Convert organizations/page.tsx**

Find the org delete handler that uses `confirm({ variant: 'danger' })`. Apply the same pattern: import `usePrivilegedActionDialog`, add hook, replace the confirm call with `privilegedAction.prompt(...)`.

**Step 4: Convert byok/page.tsx**

Find the BYOK key delete handler. Same conversion pattern.

**Step 5: Convert subscriptions/page.tsx**

Find the subscription cancel handler. Same conversion pattern.

**Step 6: Convert resource-governor/page.tsx**

Find the policy delete handler. Same conversion pattern.

**Step 7: Run affected tests**

Run: `cd /Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui && bun run vitest run app/plans/ app/organizations/ app/byok/ app/subscriptions/ app/resource-governor/`
Expected: All PASS. Some tests may need mock updates for the new `usePrivilegedActionDialog` hook. Add to mock setup:

```typescript
const privilegedActionPromptMock = vi.hoisted(() => vi.fn());

vi.mock('@/components/ui/privileged-action-dialog', () => ({
  usePrivilegedActionDialog: () => ({
    prompt: privilegedActionPromptMock,
  }),
}));
```

And in each test that triggers deletion, mock the return:
```typescript
privilegedActionPromptMock.mockResolvedValue({ reason: 'Test deletion', adminPassword: 'pass' });
```

**Step 8: Commit**

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui
git add app/plans/page.tsx app/organizations/page.tsx app/byok/page.tsx \
       app/subscriptions/page.tsx app/resource-governor/page.tsx \
       app/plans/__tests__/ app/organizations/__tests__/ app/byok/__tests__/ \
       app/subscriptions/__tests__/ app/resource-governor/__tests__/
git commit -m "feat(admin-ui): apply PrivilegedActionDialog to high-risk deletions

Tier 1 operations now require password re-auth and audit reason:
plan deletion, org deletion, BYOK key deletion, subscription
cancellation, resource governor policy deletion."
```

---

## Task 7: Quick Win — Key Hygiene Cards Clickable (3.2)

**Files:**
- Modify: `admin-ui/app/api-keys/page.tsx`

**Step 1: Make cards clickable**

In `admin-ui/app/api-keys/page.tsx`, replace each static `<Card>` (lines 293-328) with clickable versions:

Card 1 — "Keys Needing Rotation" (lines 293-301):
```tsx
<Card
  className="cursor-pointer hover:border-primary transition-colors"
  onClick={() => { updateFilter(setStatusFilter, 'active'); /* sort by age desc handled by default */ }}
>
```

Card 2 — "Expiring Soon" (lines 302-310):
```tsx
<Card
  className="cursor-pointer hover:border-primary transition-colors"
  onClick={() => updateFilter(setStatusFilter, 'active')}
>
```

Card 3 — "Inactive Keys" (lines 311-319):
```tsx
<Card
  className="cursor-pointer hover:border-primary transition-colors"
  onClick={() => updateFilter(setStatusFilter, 'active')}
>
```

Card 4 — "Hygiene Score" is informational — keep non-clickable.

**Step 2: Run tests**

Run: `cd /Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui && bun run vitest run app/api-keys/`
Expected: PASS

**Step 3: Commit**

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui
git add app/api-keys/page.tsx
git commit -m "feat(admin-ui): make API key hygiene summary cards clickable

Clicking a hygiene card applies the relevant filter to the
keys table."
```

---

## Task 8: Quick Win — Hide N/A API Key Columns (3.3)

**Files:**
- Modify: `admin-ui/components/api-keys/UnifiedApiKeysTable.tsx`

**Step 1: Add conditional column rendering**

In `admin-ui/components/api-keys/UnifiedApiKeysTable.tsx`:

a) Compute whether any row has telemetry data (near the top of the component):

```typescript
const hasTelemetry = rows.some(
  (r) => r.requestCount24h != null && Number.isFinite(r.requestCount24h)
);
```

b) Wrap the header cells (lines 103-104) in a conditional:

```tsx
{hasTelemetry && <TableHead>Requests (24h)</TableHead>}
{hasTelemetry && <TableHead>Error Rate (24h)</TableHead>}
```

c) Wrap the body cells (lines 162-163) in the same conditional:

```tsx
{hasTelemetry && <TableCell>{formatRequestCount24h(row.requestCount24h)}</TableCell>}
{hasTelemetry && <TableCell>{formatErrorRate24h(row.errorRate24h)}</TableCell>}
```

**Step 2: Run tests**

Run: `cd /Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui && bun run vitest run app/api-keys/ components/api-keys/`
Expected: PASS

**Step 3: Commit**

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui
git add components/api-keys/UnifiedApiKeysTable.tsx
git commit -m "fix(admin-ui): hide permanently-N/A API key telemetry columns

Requests (24h) and Error Rate (24h) columns now only render
when at least one row has non-null telemetry data."
```

---

## Task 9: Quick Win — Alert Button aria-labels (5.14)

**Files:**
- Modify: `admin-ui/app/monitoring/components/AlertsPanel.tsx`

**Step 1: Add aria-labels to all 4 buttons**

In `admin-ui/app/monitoring/components/AlertsPanel.tsx`:

Escalate button (line 196-204) — add `aria-label="Escalate"`:
```tsx
<Button variant="ghost" size="sm" disabled={!localActionsEnabled}
  onClick={() => onEscalate(alert)} title="Escalate" aria-label="Escalate">
```

Acknowledge button (line 208-215) — add `aria-label="Acknowledge alert"`:
```tsx
<Button variant="ghost" size="sm"
  onClick={() => onAcknowledge(alert)} title="Acknowledge" aria-label="Acknowledge alert">
```

Dismiss button (line 216-223) — add `aria-label="Dismiss alert"`:
```tsx
<Button variant="ghost" size="sm"
  onClick={() => onDismiss(alert)} title="Dismiss" aria-label="Dismiss alert">
```

Show snoozed button (line 98-107) — add `aria-label`:
```tsx
<Button type="button" variant={showSnoozed ? 'secondary' : 'outline'} size="sm"
  onClick={onToggleShowSnoozed} data-testid="alerts-show-snoozed-toggle"
  aria-label={`${showSnoozed ? 'Hide' : 'Show'} snoozed alerts (${snoozedCount})`}>
```

**Step 2: Run tests**

Run: `cd /Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui && bun run vitest run app/monitoring/`
Expected: PASS

**Step 3: Commit**

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui
git add app/monitoring/components/AlertsPanel.tsx
git commit -m "a11y(admin-ui): add aria-labels to alert panel icon buttons

Escalate, Acknowledge, Dismiss, and Show Snoozed buttons now
have aria-label attributes for screen reader accessibility."
```

---

## Task 10: Quick Win — Replace Bare Loading States (9.5)

**Files:** 13 files with 19 instances to fix.

**Step 1: Fix all 13 files**

Replace each `<div>Loading...</div>` (or similar) with the appropriate skeleton from `@/components/ui/skeleton`:

| File | Replacement |
|------|------------|
| `app/organizations/[id]/page.tsx` (2 instances) | `<CardSkeleton />` |
| `app/security/page.tsx` (1) | `<CardSkeleton />` |
| `app/providers/page.tsx` (3) | `<TableSkeleton rows={5} />` |
| `app/roles/[id]/page.tsx` (1) | `<FormSkeleton />` |
| `app/roles/matrix/page.tsx` (1) | `<TableSkeleton rows={8} cols={6} />` |
| `app/users/[id]/api-keys/page.tsx` (1) | `<TableSkeleton rows={3} />` |
| `app/teams/[id]/page.tsx` (1) | `<CardSkeleton />` |
| `app/monitoring/components/WatchlistsPanel.tsx` (1) | `<TableSkeleton rows={3} />` |
| `app/monitoring/components/NotificationsPanel.tsx` (1) | `<CardSkeleton />` |
| `app/monitoring/components/AlertsPanel.tsx` (1) | `<TableSkeleton rows={3} />` |
| `components/PermissionGuard.tsx` (1) | `<CardSkeleton />` |
| `components/data-ops/MaintenanceSection.tsx` (2) | `<CardSkeleton />` |
| `components/OrgContextSwitcher.tsx` (1) | Small inline spinner — use `<span className="text-xs text-muted-foreground">Loading...</span>` (this is a dropdown, not a page section — skeleton is inappropriate here) |

For each file:
1. Import the skeleton: `import { CardSkeleton, TableSkeleton, FormSkeleton } from '@/components/ui/skeleton';`
2. Find the loading conditional (e.g., `if (loading) return <div>Loading...</div>`)
3. Replace the return with the appropriate skeleton component

**Step 2: Run full test suite**

Run: `cd /Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui && bun run vitest run`
Expected: All PASS

**Step 3: Commit**

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui
git add app/organizations/[id]/page.tsx app/security/page.tsx app/providers/page.tsx \
       app/roles/[id]/page.tsx app/roles/matrix/page.tsx app/users/[id]/api-keys/page.tsx \
       app/teams/[id]/page.tsx app/monitoring/components/WatchlistsPanel.tsx \
       app/monitoring/components/NotificationsPanel.tsx app/monitoring/components/AlertsPanel.tsx \
       components/PermissionGuard.tsx components/data-ops/MaintenanceSection.tsx \
       components/OrgContextSwitcher.tsx
git commit -m "fix(admin-ui): replace bare Loading text with skeleton components

19 instances across 13 files now use CardSkeleton, TableSkeleton,
or FormSkeleton instead of plain 'Loading...' text."
```

---

## Task 11: Quick Win — Add ExportMenu to List Pages (9.8)

**Files:** 10 pages to add ExportMenu to.

**Step 1: Implement export handler pattern**

Each page needs:
1. Import: `import { ExportMenu, type ExportFormat } from '@/components/ui/export-menu';`
2. Handler function:

```typescript
const handleExport = (format: ExportFormat) => {
  const data = filteredItems; // or whatever the current data array is
  if (format === 'csv') {
    const headers = ['Column1', 'Column2', ...]; // match table columns
    const rows = data.map(item => [item.field1, item.field2, ...]);
    const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    downloadFile(csv, `export-${Date.now()}.csv`, 'text/csv');
  } else {
    downloadFile(JSON.stringify(data, null, 2), `export-${Date.now()}.json`, 'application/json');
  }
};

function downloadFile(content: string, filename: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
```

3. Component in page header: `<ExportMenu onExport={handleExport} disabled={items.length === 0} />`

**Step 2: Add to each page**

Apply the pattern to:
1. `app/organizations/page.tsx` — export org list
2. `app/teams/page.tsx` — export teams
3. `app/api-keys/page.tsx` — export unified keys
4. `app/logs/page.tsx` — export log entries
5. `app/budgets/page.tsx` — export budget configs
6. `app/incidents/page.tsx` — export incidents
7. `app/jobs/page.tsx` — export jobs
8. `app/voice-commands/page.tsx` — export voice commands
9. `app/acp-sessions/page.tsx` — export sessions
10. `app/subscriptions/page.tsx` — export subscriptions

Note: Create a shared `downloadFile` utility in `admin-ui/lib/export-utils.ts` to avoid repeating the download logic. Each page only needs to define `headers` and `mapRow` for CSV format.

**Step 3: Run tests**

Run: `cd /Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui && bun run vitest run`
Expected: All PASS

**Step 4: Commit**

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui
git add lib/export-utils.ts app/organizations/page.tsx app/teams/page.tsx \
       app/api-keys/page.tsx app/logs/page.tsx app/budgets/page.tsx \
       app/incidents/page.tsx app/jobs/page.tsx app/voice-commands/page.tsx \
       app/acp-sessions/page.tsx app/subscriptions/page.tsx
git commit -m "feat(admin-ui): add ExportMenu to 10 additional list pages

All major list pages now support CSV and JSON export. Shared
download utility in lib/export-utils.ts."
```

---

## Task 12: Final Verification

**Step 1: Run full test suite**

Run: `cd /Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui && bun run test`
Expected: All PASS

**Step 2: Run type check**

Run: `cd /Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui && bun run typecheck`
Expected: No errors

**Step 3: Run lint**

Run: `cd /Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui && bun run lint`
Expected: No errors

**Step 4: Build**

Run: `cd /Users/macbook-dev/Documents/GitHub/tldw_server2/admin-ui && bun run build`
Expected: Build succeeds

**Step 5: Manual smoke test**

Start the dev server and verify:
- [ ] ACP Agents page shows Invocations/Tokens/Cost columns
- [ ] ACP Agent create/edit dialog has Token Budget field
- [ ] ACP Sessions show progress bar when agent has budget
- [ ] Plans page blocks deletion when subscribers exist
- [ ] Plans deletion now requires password + reason
- [ ] API key hygiene cards are clickable and filter the table
- [ ] 24h columns are hidden when data is unavailable
- [ ] Alert buttons have aria-labels (inspect with DevTools)
- [ ] All loading states show skeletons instead of "Loading..."
- [ ] ExportMenu appears on all list pages
