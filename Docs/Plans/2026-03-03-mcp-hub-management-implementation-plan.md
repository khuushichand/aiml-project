# MCP Hub Management Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a shared WebUI/extension MCP Hub that provides full CRUD for ACP MCP server profiles, tool catalogs, and external federation servers with write-only encrypted secret handling.

**Architecture:** Implement a DB-backed MCP management control plane in FastAPI/AuthNZ, then expose a shared `apps/packages/ui` feature routed at both `/mcp-hub` and `/settings/mcp-hub`. Reuse existing MCP catalog APIs, add new ACP profile + external server APIs, enforce server-side RBAC for every mutation, and standardize audit + secret hygiene.

**Tech Stack:** FastAPI, Pydantic, AuthNZ repositories/services/migrations, SQLite/PostgreSQL compatibility helpers, React + Zustand + Ant Design in `@tldw/ui`, Next.js wrapper pages, Vitest/RTL, pytest, Bandit.

---

**Execution standards (apply to every task):**

1. Use `@test-driven-development` for all behavioral changes.
2. Use `@systematic-debugging` if any test fails unexpectedly.
3. Use `@verification-before-completion` before claiming task completion.
4. Keep commits small and task-scoped.

### Task 1: Add AuthNZ Storage for MCP Hub

**Files:**
- Modify: `tldw_Server_API/app/core/AuthNZ/migrations.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py`
- Test: `tldw_Server_API/tests/AuthNZ_SQLite/test_mcp_hub_migrations.py`
- Test: `tldw_Server_API/tests/AuthNZ_Postgres/test_mcp_hub_pg_ensure.py`

**Step 1: Write the failing tests**

```python
def test_migration_055_creates_mcp_hub_tables(sqlite_db_path):
    apply_authnz_migrations(sqlite_db_path)
    conn = sqlite3.connect(sqlite_db_path)
    names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "mcp_acp_profiles" in names
    assert "mcp_external_servers" in names
    assert "mcp_external_server_secrets" in names
```

```python
@pytest.mark.asyncio
async def test_ensure_mcp_hub_tables_pg_creates_required_tables(pg_pool):
    ok = await ensure_mcp_hub_tables_pg(pg_pool)
    assert ok is True
```

**Step 2: Run tests to verify they fail**

Run:
```bash
source .venv/bin/activate && python -m pytest -v \
  tldw_Server_API/tests/AuthNZ_SQLite/test_mcp_hub_migrations.py \
  tldw_Server_API/tests/AuthNZ_Postgres/test_mcp_hub_pg_ensure.py
```

Expected: FAIL (missing migration/ensure helpers).

**Step 3: Write minimal implementation**

```python
# migrations.py
def migration_055_create_mcp_hub_tables(conn: sqlite3.Connection) -> None:
    conn.execute("""CREATE TABLE IF NOT EXISTS mcp_acp_profiles (...)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS mcp_external_servers (...)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS mcp_external_server_secrets (...)""")
    conn.commit()
```

```python
# pg_migrations_extra.py
_CREATE_MCP_HUB_TABLES = [
    ("CREATE TABLE IF NOT EXISTS mcp_acp_profiles (...)", ()),
    ("CREATE TABLE IF NOT EXISTS mcp_external_servers (...)", ()),
    ("CREATE TABLE IF NOT EXISTS mcp_external_server_secrets (...)", ()),
]

async def ensure_mcp_hub_tables_pg(pool: DatabasePool | None = None) -> bool:
    ...
```

**Step 4: Run tests to verify they pass**

Run:
```bash
source .venv/bin/activate && python -m pytest -v \
  tldw_Server_API/tests/AuthNZ_SQLite/test_mcp_hub_migrations.py \
  tldw_Server_API/tests/AuthNZ_Postgres/test_mcp_hub_pg_ensure.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/AuthNZ/migrations.py \
  tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py \
  tldw_Server_API/tests/AuthNZ_SQLite/test_mcp_hub_migrations.py \
  tldw_Server_API/tests/AuthNZ_Postgres/test_mcp_hub_pg_ensure.py
git commit -m "feat(authnz): add mcp hub storage migrations for sqlite and postgres"
```

### Task 2: Implement MCP Hub Repository Layer

**Files:**
- Create: `tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/repos/__init__.py`
- Test: `tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_repo.py`

**Step 1: Write the failing tests**

```python
async def test_repo_can_crud_acp_profile(db_pool):
    repo = McpHubRepo(db_pool)
    created = await repo.create_acp_profile(...)
    fetched = await repo.get_acp_profile(created["id"])
    assert fetched["name"] == "default-dev"
```

```python
async def test_repo_external_server_secret_is_stored_separately(db_pool):
    repo = McpHubRepo(db_pool)
    await repo.upsert_external_server(...)
    await repo.upsert_external_secret("docs", encrypted_blob="...", key_hint="abcd")
    row = await repo.get_external_server("docs")
    assert "encrypted_blob" not in row
```

**Step 2: Run tests to verify they fail**

Run:
```bash
source .venv/bin/activate && python -m pytest -v \
  tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_repo.py
```

Expected: FAIL (repo not implemented).

**Step 3: Write minimal implementation**

```python
@dataclass
class McpHubRepo:
    db_pool: DatabasePool

    async def create_acp_profile(self, *, name: str, owner_scope_type: str, owner_scope_id: int | None, profile_json: str, actor_id: int | None) -> dict[str, Any]:
        ...

    async def list_acp_profiles(self, *, owner_scope_type: str | None, owner_scope_id: int | None) -> list[dict[str, Any]]:
        ...

    async def upsert_external_server(self, *, server_id: str, config_json: str, actor_id: int | None) -> dict[str, Any]:
        ...

    async def upsert_external_secret(self, server_id: str, *, encrypted_blob: str, key_hint: str | None, actor_id: int | None) -> dict[str, Any]:
        ...
```

**Step 4: Run tests to verify they pass**

Run:
```bash
source .venv/bin/activate && python -m pytest -v \
  tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_repo.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py \
  tldw_Server_API/app/core/AuthNZ/repos/__init__.py \
  tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_repo.py
git commit -m "feat(authnz): add mcp hub repository for profiles and external servers"
```

### Task 3: Add MCP Hub Service with Encryption + Audit

**Files:**
- Create: `tldw_Server_API/app/services/mcp_hub_service.py`
- Test: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_service.py`

**Step 1: Write the failing tests**

```python
@pytest.mark.asyncio
async def test_set_external_secret_encrypts_and_never_returns_plaintext(monkeypatch, db_pool):
    svc = McpHubService(repo=McpHubRepo(db_pool))
    out = await svc.set_external_server_secret(server_id="docs", secret_value="super-secret-token", actor_id=1)
    assert out["secret_configured"] is True
    assert "super-secret-token" not in json.dumps(out)
```

```python
@pytest.mark.asyncio
async def test_service_emits_audit_event_on_external_server_update(monkeypatch, db_pool):
    calls = []
    monkeypatch.setattr("tldw_Server_API.app.services.mcp_hub_service.emit_mcp_hub_audit", lambda **kwargs: calls.append(kwargs))
    svc = McpHubService(repo=McpHubRepo(db_pool))
    await svc.create_external_server(...)
    assert calls and calls[0]["action"] == "mcp_hub.external_server.create"
```

**Step 2: Run tests to verify they fail**

Run:
```bash
source .venv/bin/activate && python -m pytest -v \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_service.py
```

Expected: FAIL (service absent).

**Step 3: Write minimal implementation**

```python
class McpHubService:
    def __init__(self, repo: McpHubRepo):
        self.repo = repo

    async def set_external_server_secret(self, *, server_id: str, secret_value: str, actor_id: int | None) -> dict[str, Any]:
        payload = {"api_key": secret_value}
        envelope = encrypt_byok_payload(payload)
        await self.repo.upsert_external_secret(server_id, encrypted_blob=dumps_envelope(envelope), key_hint=key_hint_for_api_key(secret_value), actor_id=actor_id)
        await emit_mcp_hub_audit(action="mcp_hub.external_secret.update", actor_id=actor_id, resource_id=server_id)
        return {"server_id": server_id, "secret_configured": True}
```

**Step 4: Run tests to verify they pass**

Run:
```bash
source .venv/bin/activate && python -m pytest -v \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_service.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/services/mcp_hub_service.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_service.py
git commit -m "feat(mcp): add mcp hub service with encrypted secret handling"
```

### Task 4: Add MCP Hub API Schemas + Endpoints

**Files:**
- Create: `tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py`
- Create: `tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py`
- Modify: `tldw_Server_API/app/main.py`
- Test: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py`

**Step 1: Write the failing API tests**

```python
def test_get_mcp_hub_profiles_requires_auth(client):
    resp = client.get("/api/v1/mcp/hub/acp-profiles")
    assert resp.status_code in {401, 403}
```

```python
def test_set_external_secret_returns_masked_only(auth_client):
    resp = auth_client.post("/api/v1/mcp/hub/external-servers/docs/secret", json={"secret": "abc123secret"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["secret_configured"] is True
    assert "abc123secret" not in json.dumps(payload)
```

**Step 2: Run tests to verify they fail**

Run:
```bash
source .venv/bin/activate && python -m pytest -v \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py
```

Expected: FAIL (routes missing).

**Step 3: Write minimal implementation**

```python
router = APIRouter(prefix="/mcp/hub", tags=["mcp-hub"])

@router.get("/acp-profiles", response_model=list[ACPProfileResponse])
async def list_acp_profiles(...):
    ...

@router.post("/external-servers/{server_id}/secret", response_model=ExternalSecretSetResponse)
async def set_external_secret(server_id: str, payload: ExternalSecretSetRequest, ...):
    ...
```

```python
# main.py
from tldw_Server_API.app.api.v1.endpoints.mcp_hub_management import router as mcp_hub_router
_include_if_enabled("mcp", mcp_hub_router, prefix=f"{API_V1_PREFIX}", tags=["mcp-hub"])
```

**Step 4: Run tests to verify they pass**

Run:
```bash
source .venv/bin/activate && python -m pytest -v \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py \
  tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py \
  tldw_Server_API/app/main.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py
git commit -m "feat(api): add mcp hub management endpoints and schemas"
```

### Task 5: Add RBAC/Scope Enforcement Tests

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py`
- Test: `tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_permissions_claims.py`

**Step 1: Write the failing permission tests**

```python
def test_authenticated_user_can_view_hub_lists_but_cannot_mutate_without_claims(client_with_user_token):
    get_resp = client_with_user_token.get("/api/v1/mcp/hub/external-servers")
    assert get_resp.status_code == 200
    post_resp = client_with_user_token.post("/api/v1/mcp/hub/external-servers", json={...})
    assert post_resp.status_code == 403
```

**Step 2: Run tests to verify they fail**

Run:
```bash
source .venv/bin/activate && python -m pytest -v \
  tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_permissions_claims.py
```

Expected: FAIL (insufficient claim guards).

**Step 3: Write minimal implementation**

```python
@router.post("/external-servers", dependencies=[Depends(require_permissions("system.configure"))])
async def create_external_server(...):
    ...
```

```python
@router.get("/external-servers")
async def list_external_servers(...):
    # authenticated view allowed
    ...
```

**Step 4: Run tests to verify they pass**

Run:
```bash
source .venv/bin/activate && python -m pytest -v \
  tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_permissions_claims.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py \
  tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_permissions_claims.py
git commit -m "test(auth): enforce mcp hub claim boundaries for view and mutation"
```

### Task 6: Add Frontend MCP Hub API Client

**Files:**
- Create: `apps/packages/ui/src/services/tldw/mcp-hub.ts`
- Modify: `apps/packages/ui/src/services/tldw/index.ts`
- Test: `apps/packages/ui/src/services/tldw/__tests__/mcp-hub.test.ts`

**Step 1: Write the failing client tests**

```ts
it("maps external secret set response without exposing plaintext", async () => {
  server.use(http.post("/api/v1/mcp/hub/external-servers/docs/secret", () =>
    HttpResponse.json({ server_id: "docs", secret_configured: true, key_hint: "cdef" })
  ))
  const out = await setExternalServerSecret("docs", "my-secret")
  expect(out.secret_configured).toBe(true)
  expect(JSON.stringify(out)).not.toContain("my-secret")
})
```

**Step 2: Run tests to verify they fail**

Run:
```bash
bunx vitest run apps/packages/ui/src/services/tldw/__tests__/mcp-hub.test.ts
```

Expected: FAIL (module/functions missing).

**Step 3: Write minimal implementation**

```ts
export async function listExternalServers() {
  return tldwRequest<ExternalServerResponse[]>({ path: "/api/v1/mcp/hub/external-servers", method: "GET" })
}

export async function setExternalServerSecret(serverId: string, secret: string) {
  return tldwRequest<ExternalSecretSetResponse>({
    path: `/api/v1/mcp/hub/external-servers/${encodeURIComponent(serverId)}/secret`,
    method: "POST",
    body: { secret }
  })
}
```

**Step 4: Run tests to verify they pass**

Run:
```bash
bunx vitest run apps/packages/ui/src/services/tldw/__tests__/mcp-hub.test.ts
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/services/tldw/mcp-hub.ts \
  apps/packages/ui/src/services/tldw/index.ts \
  apps/packages/ui/src/services/tldw/__tests__/mcp-hub.test.ts
git commit -m "feat(webui): add mcp hub api client methods"
```

### Task 7: Build MCP Hub Shell + ACP Profiles Tab

**Files:**
- Create: `apps/packages/ui/src/components/Option/MCPHub/index.tsx`
- Create: `apps/packages/ui/src/components/Option/MCPHub/McpHubPage.tsx`
- Create: `apps/packages/ui/src/components/Option/MCPHub/AcpProfilesTab.tsx`
- Create: `apps/packages/ui/src/components/Option/MCPHub/__tests__/AcpProfilesTab.test.tsx`

**Step 1: Write the failing UI test**

```tsx
it("renders ACP profile list and can open create form", async () => {
  render(<McpHubPage />)
  expect(await screen.findByText("ACP Profiles")).toBeInTheDocument()
  await user.click(screen.getByRole("button", { name: /create profile/i }))
  expect(screen.getByLabelText(/profile name/i)).toBeInTheDocument()
})
```

**Step 2: Run test to verify it fails**

Run:
```bash
bunx vitest run apps/packages/ui/src/components/Option/MCPHub/__tests__/AcpProfilesTab.test.tsx
```

Expected: FAIL (components missing).

**Step 3: Write minimal implementation**

```tsx
export const McpHubPage = () => {
  const [activeTab, setActiveTab] = useState("acp-profiles")
  return <Tabs activeKey={activeTab} onChange={setActiveTab} items={[...]} />
}
```

```tsx
export const AcpProfilesTab = () => {
  const [open, setOpen] = useState(false)
  return (
    <>
      <Button onClick={() => setOpen(true)}>Create Profile</Button>
      {open ? <Form><Form.Item label="Profile Name"><Input /></Form.Item></Form> : null}
    </>
  )
}
```

**Step 4: Run test to verify it passes**

Run:
```bash
bunx vitest run apps/packages/ui/src/components/Option/MCPHub/__tests__/AcpProfilesTab.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/MCPHub/index.tsx \
  apps/packages/ui/src/components/Option/MCPHub/McpHubPage.tsx \
  apps/packages/ui/src/components/Option/MCPHub/AcpProfilesTab.tsx \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/AcpProfilesTab.test.tsx
git commit -m "feat(webui): add mcp hub shell and acp profiles tab"
```

### Task 8: Build Tool Catalogs Tab

**Files:**
- Create: `apps/packages/ui/src/components/Option/MCPHub/ToolCatalogsTab.tsx`
- Create: `apps/packages/ui/src/components/Option/MCPHub/__tests__/ToolCatalogsTab.test.tsx`

**Step 1: Write failing tab tests**

```tsx
it("switches scope and calls proper catalog loader", async () => {
  render(<ToolCatalogsTab />)
  await user.selectOptions(screen.getByLabelText(/scope/i), "org")
  expect(await screen.findByText(/org catalogs/i)).toBeInTheDocument()
})
```

**Step 2: Run tests to verify they fail**

Run:
```bash
bunx vitest run apps/packages/ui/src/components/Option/MCPHub/__tests__/ToolCatalogsTab.test.tsx
```

Expected: FAIL.

**Step 3: Write minimal implementation**

```tsx
export const ToolCatalogsTab = () => {
  const [scope, setScope] = useState<"global"|"org"|"team">("global")
  useEffect(() => { void loadCatalogs(scope) }, [scope])
  return <Select aria-label="Scope" value={scope} onChange={setScope} options={[...]} />
}
```

**Step 4: Run tests to verify they pass**

Run:
```bash
bunx vitest run apps/packages/ui/src/components/Option/MCPHub/__tests__/ToolCatalogsTab.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/MCPHub/ToolCatalogsTab.tsx \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/ToolCatalogsTab.test.tsx
git commit -m "feat(webui): add mcp hub tool catalogs tab"
```

### Task 9: Build External Servers Tab with Write-Only Secret UX

**Files:**
- Create: `apps/packages/ui/src/components/Option/MCPHub/ExternalServersTab.tsx`
- Create: `apps/packages/ui/src/components/Option/MCPHub/__tests__/ExternalServersTab.test.tsx`

**Step 1: Write failing secret-flow tests**

```tsx
it("submits secret and only displays configured state", async () => {
  render(<ExternalServersTab />)
  await user.type(screen.getByLabelText(/secret/i), "super-secret")
  await user.click(screen.getByRole("button", { name: /save secret/i }))
  expect(await screen.findByText(/secret configured/i)).toBeInTheDocument()
  expect(screen.queryByText("super-secret")).not.toBeInTheDocument()
})
```

**Step 2: Run tests to verify they fail**

Run:
```bash
bunx vitest run apps/packages/ui/src/components/Option/MCPHub/__tests__/ExternalServersTab.test.tsx
```

Expected: FAIL.

**Step 3: Write minimal implementation**

```tsx
export const ExternalServersTab = () => {
  const [secret, setSecret] = useState("")
  const [configured, setConfigured] = useState(false)
  const onSaveSecret = async () => {
    await setExternalServerSecret(activeServerId, secret)
    setSecret("")
    setConfigured(true)
  }
  ...
}
```

**Step 4: Run tests to verify they pass**

Run:
```bash
bunx vitest run apps/packages/ui/src/components/Option/MCPHub/__tests__/ExternalServersTab.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/MCPHub/ExternalServersTab.tsx \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/ExternalServersTab.test.tsx
git commit -m "feat(webui): add mcp hub external servers tab with write-only secret flow"
```

### Task 10: Wire Routes, Settings Navigation, and Next.js Pages

**Files:**
- Create: `apps/packages/ui/src/routes/option-mcp-hub.tsx`
- Modify: `apps/packages/ui/src/routes/route-registry.tsx`
- Modify: `apps/packages/ui/src/data/settings-index.ts`
- Create: `apps/tldw-frontend/pages/mcp-hub.tsx`
- Create: `apps/tldw-frontend/pages/settings/mcp-hub.tsx`
- Modify: `apps/packages/ui/src/assets/locale/en/settings.json`
- Modify: `apps/packages/ui/src/public/_locales/en/settings.json`

**Step 1: Write failing route/nav tests**

```tsx
it("registers mcp hub in route registry for both workspace and settings entry", () => {
  expect(optionRoutes.some((r) => r.path === "/mcp-hub")).toBe(true)
  expect(optionRoutes.some((r) => r.path === "/settings/mcp-hub")).toBe(true)
})
```

**Step 2: Run tests to verify they fail**

Run:
```bash
bunx vitest run apps/packages/ui/src/routes/__tests__/mcp-hub-route.test.tsx
```

Expected: FAIL.

**Step 3: Write minimal implementation**

```tsx
const OptionMcpHub = lazy(() => import("./option-mcp-hub"))
...
{ kind: "options", path: "/mcp-hub", element: <OptionMcpHub />, nav: { ... } }
{ kind: "options", path: "/settings/mcp-hub", element: <OptionMcpHub />, nav: { ... } }
```

```tsx
// Next wrappers
export default dynamic(() => import("@/routes/option-mcp-hub"), { ssr: false })
```

**Step 4: Run tests to verify they pass**

Run:
```bash
bunx vitest run apps/packages/ui/src/routes/__tests__/mcp-hub-route.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/routes/option-mcp-hub.tsx \
  apps/packages/ui/src/routes/route-registry.tsx \
  apps/packages/ui/src/data/settings-index.ts \
  apps/tldw-frontend/pages/mcp-hub.tsx \
  apps/tldw-frontend/pages/settings/mcp-hub.tsx \
  apps/packages/ui/src/assets/locale/en/settings.json \
  apps/packages/ui/src/public/_locales/en/settings.json \
  apps/packages/ui/src/routes/__tests__/mcp-hub-route.test.tsx
git commit -m "feat(routes): wire mcp hub workspace and settings routes"
```

### Task 11: Add End-to-End Backend + Frontend Flow Tests

**Files:**
- Create: `tldw_Server_API/tests/server_e2e_tests/test_mcp_hub_workflow.py`
- Create: `apps/packages/ui/src/components/Option/MCPHub/__tests__/McpHubPage.integration.test.tsx`

**Step 1: Write failing integration tests**

```python
def test_mcp_hub_external_server_full_workflow(auth_client):
    create = auth_client.post("/api/v1/mcp/hub/external-servers", json={...})
    assert create.status_code == 201
    secret = auth_client.post("/api/v1/mcp/hub/external-servers/docs/secret", json={"secret": "abc"})
    assert secret.status_code == 200
    listing = auth_client.get("/api/v1/mcp/hub/external-servers").json()
    assert "abc" not in json.dumps(listing)
```

```tsx
it("runs create profile -> create external server -> set secret flow", async () => {
  render(<McpHubPage />)
  ...
  expect(await screen.findByText(/secret configured/i)).toBeInTheDocument()
})
```

**Step 2: Run tests to verify they fail**

Run:
```bash
source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/server_e2e_tests/test_mcp_hub_workflow.py
bunx vitest run apps/packages/ui/src/components/Option/MCPHub/__tests__/McpHubPage.integration.test.tsx
```

Expected: FAIL.

**Step 3: Write minimal implementation adjustments**

```python
# tighten response sanitization and route contracts where integration reveals gaps
```

```tsx
// fill missing UI loading/error state transitions required by integration test
```

**Step 4: Run tests to verify they pass**

Run:
```bash
source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/server_e2e_tests/test_mcp_hub_workflow.py
bunx vitest run apps/packages/ui/src/components/Option/MCPHub/__tests__/McpHubPage.integration.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/server_e2e_tests/test_mcp_hub_workflow.py \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/McpHubPage.integration.test.tsx
git commit -m "test(mcp-hub): add end-to-end workflow coverage"
```

### Task 12: Security Verification, Final Test Sweep, and Docs

**Files:**
- Modify: `Docs/MCP/Unified/User_Guide.md`
- Modify: `Docs/Development/Agent_Client_Protocol.md`
- Optional: `README.md` (only if route listing is maintained there)

**Step 1: Write failing doc/assertion checks**

```bash
rg -n "/api/v1/mcp/hub|/mcp-hub" Docs/MCP/Unified/User_Guide.md Docs/Development/Agent_Client_Protocol.md
# expected: no matches before docs update
```

**Step 2: Run verification commands before finalizing**

Run:
```bash
source .venv/bin/activate && python -m pytest -v \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py \
  tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_permissions_claims.py \
  tldw_Server_API/tests/server_e2e_tests/test_mcp_hub_workflow.py

bunx vitest run \
  apps/packages/ui/src/services/tldw/__tests__/mcp-hub.test.ts \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/AcpProfilesTab.test.tsx \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/ToolCatalogsTab.test.tsx \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/ExternalServersTab.test.tsx \
  apps/packages/ui/src/routes/__tests__/mcp-hub-route.test.tsx

source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py \
  tldw_Server_API/app/services/mcp_hub_service.py \
  tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py \
  -f json -o /tmp/bandit_mcp_hub.json
```

Expected: targeted tests PASS, Bandit no new actionable findings.

**Step 3: Write minimal implementation/doc fixes if verification fails**

```markdown
# Add MCP Hub endpoint and route references to docs
```

**Step 4: Re-run verification to confirm green**

Run the same commands from Step 2.

Expected: PASS.

**Step 5: Commit**

```bash
git add Docs/MCP/Unified/User_Guide.md Docs/Development/Agent_Client_Protocol.md /tmp/bandit_mcp_hub.json
git commit -m "docs(security): document mcp hub routes and verify with bandit"
```

