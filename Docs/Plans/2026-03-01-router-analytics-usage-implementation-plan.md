# Router Analytics Usage View Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace `/usage` with a TokenRouter-style operations view backed by new aggregate `router-analytics` APIs, starting with `Status` and scaffolding all tabs.

**Architecture:** Add additive backend endpoints under `/api/v1/admin/router-analytics/*` that return pre-aggregated tab payloads and freshness metadata. Extend LLM usage logging with `remote_ip`, `user_agent`, `token_name`, and optional `conversation_id`; then keep the frontend thin by rendering typed payloads with minimal client-side computation.

**Tech Stack:** FastAPI, Pydantic, AuthNZ SQLite/Postgres migrations, existing admin services, Next.js App Router, React 19, TypeScript, Recharts, Vitest, Pytest.

## Execution Corrections (Required)

- Migration must be explicitly registered in AuthNZ migration registry (`get_authnz_migrations`) with a concrete number (use `054`) or it will not run.
- Do not use non-existent test fixtures (for example `sqlite_db_pool`). Use explicit env + `reset_db_pool` + `ensure_authnz_tables(Path(pool.db_path))` patterns already used in this repo.
- Router analytics endpoint tests must include valid admin auth setup (single-user API key header) to avoid false failures from auth guards.
- Preserve existing privacy behavior for IP/UA telemetry:
  - Respect `PII_REDACT_LOGS` and `USAGE_LOG_DISABLE_META`.
  - Apply trusted-proxy IP resolution rules consistently with existing middleware behavior.
- Add explicit org-scope assertions for new router-analytics service/endpoints (not only happy-path aggregation assertions).
- Preserve `/usage` deep-link compatibility during migration (`group_by`/legacy filters should map to new `tab`/filters).
- Fix client query construction bug risk: build URLs as `.../status${qs ? \`?\${qs}\` : ''}`.
- Final docs commit in Task 9 is conditional: commit only if files changed.

---

### Task 1: Add Router Analytics API Schemas

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/admin_schemas.py`
- Create: `tldw_Server_API/tests/Admin/test_router_analytics_schemas.py`
- Test: `tldw_Server_API/tests/Admin/test_router_analytics_schemas.py`

**Step 1: Write the failing test**

```python
from pydantic import ValidationError
from tldw_Server_API.app.api.v1.schemas.admin_schemas import RouterAnalyticsRangeQuery

def test_router_analytics_range_rejects_invalid_value():
    try:
        RouterAnalyticsRangeQuery(range="2h")
    except ValidationError as exc:
        assert "range" in str(exc)
    else:
        assert False, "expected ValidationError"
```

**Step 2: Run test to verify it fails**

Run:
```bash
source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Admin/test_router_analytics_schemas.py::test_router_analytics_range_rejects_invalid_value
```
Expected: FAIL with import/model missing errors.

**Step 3: Write minimal implementation**

```python
class RouterAnalyticsRangeQuery(BaseModel):
    range: Literal["realtime", "1h", "8h", "24h", "7d", "30d"] = "8h"
```

Also add:
- `RouterAnalyticsStatusResponse`
- `RouterAnalyticsBreakdownsResponse`
- Shared item rows (`RouterAnalyticsBreakdownRow`, `RouterAnalyticsSeriesPoint`, etc.)

**Step 4: Run test to verify it passes**

Run:
```bash
source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Admin/test_router_analytics_schemas.py
```
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/admin_schemas.py tldw_Server_API/tests/Admin/test_router_analytics_schemas.py
git commit -m "test+feat(admin): add router analytics schema models"
```

---

### Task 2: Add `llm_usage_log` Columns + Indexes (SQLite and Postgres)

**Files:**
- Modify: `tldw_Server_API/app/core/AuthNZ/migrations.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py`
- Create: `tldw_Server_API/tests/AuthNZ_SQLite/test_authnz_llm_usage_log_router_columns_sqlite.py`
- Create: `tldw_Server_API/tests/AuthNZ_Postgres/test_authnz_llm_usage_log_router_columns_pg.py`
- Test: `tldw_Server_API/tests/AuthNZ_SQLite/test_authnz_llm_usage_log_router_columns_sqlite.py`

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_llm_usage_log_has_router_analytics_columns_sqlite(tmp_path, monkeypatch):
    # Use existing repo test pattern: env -> reset pool -> ensure schema.
    ...
    cols = {row["name"] for row in await pool.fetchall("PRAGMA table_info(llm_usage_log)")}
    assert {"remote_ip", "user_agent", "token_name", "conversation_id"}.issubset(cols)
```

**Step 2: Run test to verify it fails**

Run:
```bash
source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/AuthNZ_SQLite/test_authnz_llm_usage_log_router_columns_sqlite.py
```
Expected: FAIL because columns do not exist.

**Step 3: Write minimal implementation**

```python
def migration_054_add_llm_usage_log_router_analytics_columns(conn: sqlite3.Connection) -> None:
    conn.execute("ALTER TABLE llm_usage_log ADD COLUMN remote_ip TEXT")
    conn.execute("ALTER TABLE llm_usage_log ADD COLUMN user_agent TEXT")
    conn.execute("ALTER TABLE llm_usage_log ADD COLUMN token_name TEXT")
    conn.execute("ALTER TABLE llm_usage_log ADD COLUMN conversation_id TEXT")
```

And in Postgres migration path:
```sql
ALTER TABLE llm_usage_log ADD COLUMN IF NOT EXISTS remote_ip TEXT;
ALTER TABLE llm_usage_log ADD COLUMN IF NOT EXISTS user_agent TEXT;
ALTER TABLE llm_usage_log ADD COLUMN IF NOT EXISTS token_name TEXT;
ALTER TABLE llm_usage_log ADD COLUMN IF NOT EXISTS conversation_id TEXT;
CREATE INDEX IF NOT EXISTS idx_llm_usage_log_remote_ip_ts ON llm_usage_log(remote_ip, ts);
CREATE INDEX IF NOT EXISTS idx_llm_usage_log_token_name_ts ON llm_usage_log(token_name, ts);
```

Also required:
- Register migration `054` in `get_authnz_migrations()` list.
- Extend Postgres ensure path in `pg_migrations_extra.py` with `ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...` entries so existing PG tables are upgraded idempotently.

**Step 4: Run test to verify it passes**

Run:
```bash
source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/AuthNZ_SQLite/test_authnz_llm_usage_log_router_columns_sqlite.py
source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/AuthNZ_Postgres/test_authnz_llm_usage_log_router_columns_pg.py
```
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/AuthNZ/migrations.py tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py tldw_Server_API/tests/AuthNZ_SQLite/test_authnz_llm_usage_log_router_columns_sqlite.py tldw_Server_API/tests/AuthNZ_Postgres/test_authnz_llm_usage_log_router_columns_pg.py
git commit -m "feat(authnz): add llm usage router analytics columns and indexes"
```

---

### Task 3: Thread Enrichment Through Usage Logging (`log_llm_usage`)

**Files:**
- Modify: `tldw_Server_API/app/core/Usage/usage_tracker.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/repos/usage_repo.py`
- Modify: `tldw_Server_API/app/core/Chat/chat_service.py`
- Modify: `tldw_Server_API/app/core/Claims_Extraction/claims_engine.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/embeddings_v5_production_enhanced.py`
- Modify: `tldw_Server_API/tests/Usage/test_usage_tracker_sqlite.py`
- Test: `tldw_Server_API/tests/Usage/test_usage_tracker_sqlite.py`

**Step 1: Write the failing test**

```python
async def test_log_llm_usage_persists_router_enrichment(tmp_usage_db):
    await log_llm_usage(
        user_id=1, key_id=1, endpoint="/chat", operation="chat", provider="openai", model="gpt-4o-mini",
        status=200, latency_ms=120, prompt_tokens=10, completion_tokens=5,
        remote_ip="127.0.0.1", user_agent="pytest-agent/1.0", token_name="Admin", conversation_id="conv-1"
    )
    row = await fetch_latest_llm_usage_log_row()
    assert row["remote_ip"] == "127.0.0.1"
```

**Step 2: Run test to verify it fails**

Run:
```bash
source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Usage/test_usage_tracker_sqlite.py::test_log_llm_usage_persists_router_enrichment
```
Expected: FAIL due function signature / insert mismatch.

**Step 3: Write minimal implementation**

```python
async def log_llm_usage(..., request: Request | None = None, remote_ip: str | None = None, user_agent: str | None = None, token_name: str | None = None, conversation_id: str | None = None):
    # Derive remote_ip/user_agent from request when not explicitly supplied.
    # Respect privacy toggles (PII_REDACT_LOGS, USAGE_LOG_DISABLE_META).
    # Resolve token_name from api_keys.name using key_id when token_name is not supplied.
    await repo.insert_llm_usage_log(..., remote_ip=remote_ip, user_agent=user_agent, token_name=token_name, conversation_id=conversation_id)
```

Update `insert_llm_usage_log` SQL columns in repo accordingly.

**Step 4: Run test to verify it passes**

Run:
```bash
source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Usage/test_usage_tracker_sqlite.py
```
Expected: PASS for touched tests.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Usage/usage_tracker.py tldw_Server_API/app/core/AuthNZ/repos/usage_repo.py tldw_Server_API/app/core/Chat/chat_service.py tldw_Server_API/app/core/Claims_Extraction/claims_engine.py tldw_Server_API/app/api/v1/endpoints/embeddings_v5_production_enhanced.py tldw_Server_API/tests/Usage/test_usage_tracker_sqlite.py
git commit -m "feat(usage): persist remote ip, user agent, token name, conversation id"
```

---

### Task 4: Implement Router Analytics Service (Status + Breakdowns + Meta)

**Files:**
- Create: `tldw_Server_API/app/services/admin_router_analytics_service.py`
- Modify: `tldw_Server_API/app/services/__init__.py`
- Create: `tldw_Server_API/tests/Admin/test_admin_router_analytics_service.py`
- Test: `tldw_Server_API/tests/Admin/test_admin_router_analytics_service.py`

**Step 1: Write the failing test**

```python
async def test_build_status_payload_returns_kpis_and_series(seed_llm_usage_logs):
    payload = await get_router_status(db=seed_llm_usage_logs, range="8h")
    assert payload["kpis"]["requests"] > 0
    assert isinstance(payload["series"], list)
```

**Step 2: Run test to verify it fails**

Run:
```bash
source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Admin/test_admin_router_analytics_service.py
```
Expected: FAIL (module/function missing).

**Step 3: Write minimal implementation**

```python
async def get_router_status(*, principal, db, range, org_id=None, provider=None, model=None, token_id=None, granularity=None):
    # normalize window
    # aggregate kpis from llm_usage_log
    # build bucketed series grouped by model/provider
    return {"kpis": {...}, "series": [...], "providers_available": 0, "providers_online": 0, "generated_at": "..."}
```

Add:
- `get_router_status_breakdowns(...)`
- `get_router_meta(...)`

Service tests must include:
- org-scope filtering behavior (only rows from authorized orgs appear)
- out-of-scope `org_id` request returns empty dataset (not cross-org leakage)

**Step 4: Run test to verify it passes**

Run:
```bash
source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Admin/test_admin_router_analytics_service.py
```
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/services/admin_router_analytics_service.py tldw_Server_API/app/services/__init__.py tldw_Server_API/tests/Admin/test_admin_router_analytics_service.py
git commit -m "feat(admin): add router analytics aggregate service for status views"
```

---

### Task 5: Add Router Analytics Endpoints and Wire Admin Router

**Files:**
- Create: `tldw_Server_API/app/api/v1/endpoints/admin/admin_router_analytics.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/admin/__init__.py`
- Modify: `tldw_Server_API/tests/Admin/test_admin_split_openapi_contract.py`
- Create: `tldw_Server_API/tests/Admin/test_router_analytics_endpoints.py`
- Test: `tldw_Server_API/tests/Admin/test_router_analytics_endpoints.py`

**Step 1: Write the failing test**

```python
def test_router_analytics_status_endpoint_exists(monkeypatch, tmp_path):
    with TestClient(app, headers={"X-API-KEY": "unit-test-api-key-router"}) as client:
        r = client.get("/api/v1/admin/router-analytics/status?range=8h")
    assert r.status_code == 200
```

**Step 2: Run test to verify it fails**

Run:
```bash
source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Admin/test_router_analytics_endpoints.py::test_router_analytics_status_endpoint_exists
```
Expected: FAIL with 404 or route missing.

**Step 3: Write minimal implementation**

```python
router = APIRouter()

@router.get("/router-analytics/status", response_model=RouterAnalyticsStatusResponse)
async def get_router_analytics_status(...):
    return await admin_router_analytics_service.get_router_status(...)
```

Also add:
- `/router-analytics/status/breakdowns`
- `/router-analytics/meta`
- stubs for remaining tabs returning typed placeholder payloads
- endpoint-level org-scope assertions (`org_id` in-scope vs out-of-scope)

**Step 4: Run test to verify it passes**

Run:
```bash
source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Admin/test_router_analytics_endpoints.py tldw_Server_API/tests/Admin/test_admin_split_openapi_contract.py
```
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/admin/admin_router_analytics.py tldw_Server_API/app/api/v1/endpoints/admin/__init__.py tldw_Server_API/tests/Admin/test_router_analytics_endpoints.py tldw_Server_API/tests/Admin/test_admin_split_openapi_contract.py
git commit -m "feat(admin-api): expose router analytics endpoints under /admin/router-analytics"
```

---

### Task 6: Add Admin UI Client Layer for Router Analytics

**Files:**
- Create: `admin-ui/lib/router-analytics-types.ts`
- Create: `admin-ui/lib/router-analytics-client.ts`
- Modify: `admin-ui/lib/api-client.ts`
- Create: `admin-ui/lib/router-analytics-client.test.ts`
- Test: `admin-ui/lib/router-analytics-client.test.ts`

**Step 1: Write the failing test**

```ts
it("builds status URL with range and provider filters", async () => {
  await getRouterStatus({ range: "8h", provider: "openai" });
  expect(requestJson).toHaveBeenCalledWith("/admin/router-analytics/status?range=8h&provider=openai");
});
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd admin-ui && bunx vitest run lib/router-analytics-client.test.ts
```
Expected: FAIL module/function missing.

**Step 3: Write minimal implementation**

```ts
export const getRouterStatus = (params: RouterAnalyticsQuery) =>
  requestJson(`/admin/router-analytics/status${(qs => (qs ? `?${qs}` : ""))(buildQueryString(params))}`);
```

Add typed methods:
- `getRouterStatusBreakdowns`
- `getRouterMeta`
- tab-specific calls for future steps

**Step 4: Run test to verify it passes**

Run:
```bash
cd admin-ui && bunx vitest run lib/router-analytics-client.test.ts
```
Expected: PASS.

**Step 5: Commit**

```bash
git add admin-ui/lib/router-analytics-types.ts admin-ui/lib/router-analytics-client.ts admin-ui/lib/api-client.ts admin-ui/lib/router-analytics-client.test.ts
git commit -m "feat(admin-ui): add typed router analytics API client"
```

---

### Task 7: Rebuild `/usage` as Thin Tab Shell + Status Tab (Step 1 Delivery)

**Files:**
- Modify: `admin-ui/app/usage/page.tsx`
- Create: `admin-ui/app/usage/components/RouterUsageHeader.tsx`
- Create: `admin-ui/app/usage/components/RouterUsageTabs.tsx`
- Create: `admin-ui/app/usage/components/status/StatusKpiCards.tsx`
- Create: `admin-ui/app/usage/components/status/StatusUsageChart.tsx`
- Create: `admin-ui/app/usage/components/status/StatusBreakdownTables.tsx`
- Modify: `admin-ui/app/usage/__tests__/page.test.tsx`
- Create: `admin-ui/app/usage/__tests__/status-tab.test.tsx`
- Test: `admin-ui/app/usage/__tests__/status-tab.test.tsx`

Migration note:
- Replace old `/usage` test assertions that target removed tabs/content (`Endpoints`, `LLM Usage`) with router-analytics shell/status assertions.

**Step 1: Write the failing test**

```ts
it("renders Status tab cards and breakdown tables from router analytics payload", async () => {
  render(<UsagePage />);
  expect(await screen.findByText("Usage Stats")).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Status" })).toHaveAttribute("aria-selected", "true");
});
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd admin-ui && bunx vitest run app/usage/__tests__/status-tab.test.tsx
```
Expected: FAIL due old layout/component mismatch.

**Step 3: Write minimal implementation**

```tsx
<RouterUsageTabs
  activeTab={tab}
  tabs={["status","quota","providers","access","network","models","conversations","log"]}
>
  <StatusKpiCards data={status.kpis} />
  <StatusUsageChart points={status.series} />
  <StatusBreakdownTables data={breakdowns} />
</RouterUsageTabs>
```

**Step 4: Run test to verify it passes**

Run:
```bash
cd admin-ui && bunx vitest run app/usage/__tests__/status-tab.test.tsx app/usage/__tests__/page.test.tsx
```
Expected: PASS.

**Step 5: Commit**

```bash
git add admin-ui/app/usage/page.tsx admin-ui/app/usage/components/RouterUsageHeader.tsx admin-ui/app/usage/components/RouterUsageTabs.tsx admin-ui/app/usage/components/status admin-ui/app/usage/__tests__/page.test.tsx admin-ui/app/usage/__tests__/status-tab.test.tsx
git commit -m "feat(admin-ui): ship router analytics status tab on /usage"
```

---

### Task 8: Add Placeholder Tabs + URL State + Step Labels

**Files:**
- Modify: `admin-ui/app/usage/page.tsx`
- Create: `admin-ui/app/usage/components/ComingSoonTabPanel.tsx`
- Modify: `admin-ui/app/providers/page.tsx`
- Modify: `admin-ui/app/usage/__tests__/page.test.tsx`
- Create: `admin-ui/app/usage/__tests__/tabs-sequencing.test.tsx`
- Create: `admin-ui/app/usage/__tests__/legacy-query-compat.test.tsx`
- Test: `admin-ui/app/usage/__tests__/tabs-sequencing.test.tsx`

**Step 1: Write the failing test**

```ts
it("shows all tabs and marks non-status tabs as coming soon", async () => {
  render(<UsagePage />);
  expect(screen.getByRole("tab", { name: "Quota" })).toBeInTheDocument();
  expect(screen.getByText("Available in Step 2")).toBeInTheDocument();
});
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd admin-ui && bunx vitest run app/usage/__tests__/tabs-sequencing.test.tsx
```
Expected: FAIL because placeholder state not implemented.

**Step 3: Write minimal implementation**

```tsx
const TAB_STEPS = { status: 1, quota: 2, providers: 3, access: 4, network: 5, models: 6, conversations: 7, log: 8 } as const;
```

Render unfinished tabs with:
- disabled content panel
- `Available in Step N` marker
- URL state preserved via `?tab=...`
- legacy query compatibility mapping preserved (`group_by`, `provider`, `model`) so old deep links still open meaningful tab/filter state.

**Step 4: Run test to verify it passes**

Run:
```bash
cd admin-ui && bunx vitest run app/usage/__tests__/tabs-sequencing.test.tsx app/usage/__tests__/page.test.tsx app/usage/__tests__/legacy-query-compat.test.tsx
```
Expected: PASS.

**Step 5: Commit**

```bash
git add admin-ui/app/usage/page.tsx admin-ui/app/usage/components/ComingSoonTabPanel.tsx admin-ui/app/providers/page.tsx admin-ui/app/usage/__tests__/tabs-sequencing.test.tsx admin-ui/app/usage/__tests__/page.test.tsx admin-ui/app/usage/__tests__/legacy-query-compat.test.tsx
git commit -m "feat(admin-ui): add phased tab sequencing for router analytics usage page"
```

---

### Task 9: Verification, Security Scan, and Documentation Touch-Ups

**Files:**
- Modify: `admin-ui/README.md` (if endpoint references added)
- Modify: `Docs/Plans/2026-03-01-router-analytics-usage-design.md` (if implementation deltas discovered)
- Create: `/tmp/bandit_router_analytics.json` (artifact only, not committed)
- Test: touched backend/frontend suites

**Step 1: Write the failing test (verification checkpoint)**

Use existing touched tests as the gate:
- `tldw_Server_API/tests/Admin/test_router_analytics_endpoints.py`
- `admin-ui/app/usage/__tests__/status-tab.test.tsx`

**Step 2: Run tests and verify any failures**

Run:
```bash
source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Admin/test_router_analytics_endpoints.py tldw_Server_API/tests/Admin/test_admin_router_analytics_service.py
cd admin-ui && bunx vitest run app/usage/__tests__/status-tab.test.tsx app/usage/__tests__/tabs-sequencing.test.tsx lib/router-analytics-client.test.ts
```
Expected: PASS (or actionable failures to fix before merge).

**Step 3: Run security scan on touched backend paths**

Run:
```bash
source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/endpoints/admin/admin_router_analytics.py tldw_Server_API/app/services/admin_router_analytics_service.py tldw_Server_API/app/core/Usage/usage_tracker.py -f json -o /tmp/bandit_router_analytics.json
```

If findings are in changed code, fix them before final commit.

**Step 4: Re-run tests to confirm clean state**

Repeat Task 9 Step 2 commands.

**Step 5: Commit**

```bash
git add admin-ui/README.md Docs/Plans/2026-03-01-router-analytics-usage-design.md
git diff --cached --quiet || git commit -m "docs: finalize router analytics verification notes"
```

---

## Notes for Execution

- Use `@test-driven-development` discipline on every task.
- Keep commits small and aligned to one task each.
- Prefer additive changes; do not break existing `/admin/usage/*` and `/admin/llm-usage*` behavior.
- For large `admin-ui/app/usage/page.tsx`, prefer extraction into small components over in-file complexity.
- Preserve existing RBAC and org scoping behavior.
