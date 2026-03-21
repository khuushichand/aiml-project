# Integrations And Scheduled Tasks Control Plane Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a backend control plane plus shared web UI/extension management surfaces for personal integrations, workspace integrations, and unified scheduled tasks.

**Architecture:** Add typed backend control-plane endpoints on top of the existing Slack, Discord, Telegram, reminders, and watchlists domains. Persist a new workspace-scoped installation registry for Slack and Discord, extend Telegram admin management with linked-actor inventory/revoke support, then build shared `packages/ui` routes/components consumed by both the Next.js web UI and the extension options UI.

**Tech Stack:** FastAPI, Pydantic, existing AuthNZ repos, React, TypeScript, TanStack Query, Vitest, Playwright, pytest, Bandit

## Progress

- Task 1: Complete
- Task 2: Complete
- Task 3: Complete
- Task 4: Complete
- Task 5: Complete
- Task 6: Complete
- Task 7: Complete
- Task 8: In Progress
- Task 9: Not Started

---

### Task 1: Create The Workspace Installation Registry Repo

**Files:**
- Create: `tldw_Server_API/app/core/AuthNZ/repos/workspace_provider_installations_repo.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/repos/__init__.py`
- Test: `tldw_Server_API/tests/Integrations/test_workspace_provider_installations_repo.py`

**Step 1: Write the failing test**

```python
async def test_upsert_and_list_workspace_installations_round_trip():
    repo = await get_workspace_provider_installations_repo()

    await repo.upsert_installation(
        org_id=1,
        provider="slack",
        external_id="T123",
        display_name="Acme Slack",
        installed_by_user_id=7,
        disabled=False,
    )

    rows = await repo.list_installations(org_id=1, provider="slack")
    assert rows[0]["external_id"] == "T123"
    assert rows[0]["installed_by_user_id"] == 7
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Integrations/test_workspace_provider_installations_repo.py -v
```

Expected: FAIL because `workspace_provider_installations_repo.py` and its helpers do not exist yet.

**Step 3: Write minimal implementation**

```python
class WorkspaceProviderInstallationsRepo:
    async def upsert_installation(...): ...
    async def list_installations(...): ...
    async def set_disabled(...): ...
    async def delete_installation(...): ...
```

Include table bootstrap for both SQLite and Postgres paths, following the style used by the existing AuthNZ repos.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Integrations/test_workspace_provider_installations_repo.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/AuthNZ/repos/workspace_provider_installations_repo.py tldw_Server_API/app/core/AuthNZ/repos/__init__.py tldw_Server_API/tests/Integrations/test_workspace_provider_installations_repo.py
git commit -m "feat: add workspace provider installation registry repo"
```

### Task 2: Persist Slack And Discord Installations Into The Registry

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/slack_oauth_admin.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/discord_oauth_admin.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/slack.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/discord.py`
- Test: `tldw_Server_API/tests/Integrations/test_workspace_installation_registry_callbacks.py`

**Step 1: Write the failing test**

```python
async def test_slack_oauth_callback_persists_workspace_registry_row(...):
    result = await slack_oauth_callback_impl(...)
    rows = await registry_repo.list_installations(org_id=1, provider="slack")
    assert result["status"] == "installed"
    assert rows[0]["external_id"] == "T123"
```

Add the Discord twin in the same test module.

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Integrations/test_workspace_installation_registry_callbacks.py -v
```

Expected: FAIL because the OAuth callback code does not yet persist workspace-visible installation rows.

**Step 3: Write minimal implementation**

```python
await workspace_registry.upsert_installation(
    org_id=resolved_org_id,
    provider="slack",
    external_id=team_id,
    display_name=team_name,
    installed_by_user_id=user_id,
    disabled=False,
)
```

Mirror the same behavior for Discord, and update disable/remove handlers so registry rows stay in sync with installation state changes.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Integrations/test_workspace_installation_registry_callbacks.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/slack_oauth_admin.py tldw_Server_API/app/api/v1/endpoints/discord_oauth_admin.py tldw_Server_API/app/api/v1/endpoints/slack.py tldw_Server_API/app/api/v1/endpoints/discord.py tldw_Server_API/tests/Integrations/test_workspace_installation_registry_callbacks.py
git commit -m "feat: sync slack and discord oauth installs into workspace registry"
```

### Task 3: Add Telegram Linked-Actor Inventory And Revoke Support

**Files:**
- Modify: `tldw_Server_API/app/core/AuthNZ/repos/telegram_runtime_repo.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/telegram_schemas.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/telegram_support.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/telegram.py`
- Test: `tldw_Server_API/tests/Telegram/test_telegram_admin_link_inventory.py`

**Step 1: Write the failing test**

```python
async def test_admin_can_list_and_revoke_linked_telegram_actors(...):
    rows = await telegram_admin_list_linked_actors_impl(...)
    assert rows["items"][0]["telegram_user_id"] == 123456

    result = await telegram_admin_revoke_linked_actor_impl(actor_id=rows["items"][0]["id"], ...)
    assert result["deleted"] is True
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Telegram/test_telegram_admin_link_inventory.py -v
```

Expected: FAIL because list/revoke helpers and endpoints do not exist yet.

**Step 3: Write minimal implementation**

```python
class TelegramRuntimeRepo:
    async def list_actor_links(self, scope_type: str, scope_id: int) -> list[dict[str, Any]]: ...
    async def delete_actor_link(self, link_id: int) -> bool: ...
```

Wire those repo methods into admin-only endpoint helpers and typed response models.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Telegram/test_telegram_admin_link_inventory.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/AuthNZ/repos/telegram_runtime_repo.py tldw_Server_API/app/api/v1/schemas/telegram_schemas.py tldw_Server_API/app/api/v1/endpoints/telegram_support.py tldw_Server_API/app/api/v1/endpoints/telegram.py tldw_Server_API/tests/Telegram/test_telegram_admin_link_inventory.py
git commit -m "feat: add telegram linked-actor admin inventory and revoke"
```

### Task 4: Add Typed Control-Plane Schemas And Integrations Service

**Files:**
- Create: `tldw_Server_API/app/api/v1/schemas/integrations_control_plane_schemas.py`
- Create: `tldw_Server_API/app/services/integrations_control_plane_service.py`
- Test: `tldw_Server_API/tests/Integrations/test_integrations_control_plane_service.py`

**Step 1: Write the failing test**

```python
def test_workspace_integrations_service_normalizes_slack_discord_and_telegram():
    service = IntegrationsControlPlaneService(...)
    payload = service.build_workspace_overview(org_id=1, user_id=7)

    assert {item.provider for item in payload.items} == {"slack", "discord", "telegram"}
    assert all(item.scope == "workspace" for item in payload.items)
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Integrations/test_integrations_control_plane_service.py -v
```

Expected: FAIL because the control-plane service and schemas do not exist yet.

**Step 3: Write minimal implementation**

```python
class IntegrationConnection(BaseModel):
    id: str
    provider: Literal["slack", "discord", "telegram"]
    scope: Literal["personal", "workspace"]
    display_name: str
    status: str
    enabled: bool
    metadata: dict[str, Any] = Field(default_factory=dict)
    actions: list[str] = Field(default_factory=list)
```

Implement the service methods that normalize provider-specific state into the typed models.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Integrations/test_integrations_control_plane_service.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/integrations_control_plane_schemas.py tldw_Server_API/app/services/integrations_control_plane_service.py tldw_Server_API/tests/Integrations/test_integrations_control_plane_service.py
git commit -m "feat: add typed integrations control plane service"
```

### Task 5: Add The Integrations Control-Plane Endpoints

**Files:**
- Create: `tldw_Server_API/app/api/v1/endpoints/integrations_control_plane.py`
- Modify: `tldw_Server_API/app/main.py`
- Test: `tldw_Server_API/tests/Integrations/test_integrations_control_plane_endpoints.py`

**Step 1: Write the failing test**

```python
async def test_get_personal_integrations_returns_normalized_payload(client, auth_headers):
    response = await client.get("/api/v1/integrations/personal", headers=auth_headers)
    assert response.status_code == 200
    assert "items" in response.json()
```

Add admin coverage for `/api/v1/integrations/workspace` and `/api/v1/integrations/workspace/telegram/linked-actors`.

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Integrations/test_integrations_control_plane_endpoints.py -v
```

Expected: FAIL because the router is not registered.

**Step 3: Write minimal implementation**

```python
router = APIRouter(prefix="/integrations", tags=["integrations"])

@router.get("/personal")
async def list_personal_integrations(...): ...

@router.get("/workspace")
async def list_workspace_integrations(...): ...
```

Include typed admin-only mutation endpoints for workspace policy and Telegram management.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Integrations/test_integrations_control_plane_endpoints.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/integrations_control_plane.py tldw_Server_API/app/main.py tldw_Server_API/tests/Integrations/test_integrations_control_plane_endpoints.py
git commit -m "feat: add integrations control plane endpoints"
```

### Task 6: Add The Scheduled-Tasks Control-Plane Service And Endpoints

**Files:**
- Create: `tldw_Server_API/app/api/v1/schemas/scheduled_tasks_control_plane_schemas.py`
- Create: `tldw_Server_API/app/services/scheduled_tasks_control_plane_service.py`
- Create: `tldw_Server_API/app/api/v1/endpoints/scheduled_tasks_control_plane.py`
- Modify: `tldw_Server_API/app/main.py`
- Test: `tldw_Server_API/tests/Reminders/test_scheduled_tasks_control_plane.py`

**Step 1: Write the failing test**

```python
async def test_scheduled_tasks_endpoint_combines_reminders_and_watchlist_jobs(client, auth_headers):
    response = await client.get("/api/v1/scheduled-tasks", headers=auth_headers)
    body = response.json()

    assert response.status_code == 200
    assert {item["primitive"] for item in body["items"]} == {"reminder_task", "watchlist_job"}
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Reminders/test_scheduled_tasks_control_plane.py -v
```

Expected: FAIL because the endpoint and service do not exist yet.

**Step 3: Write minimal implementation**

```python
class ScheduledTask(BaseModel):
    id: str
    primitive: Literal["reminder_task", "watchlist_job"]
    title: str
    status: str
    edit_mode: Literal["native", "external"]
    manage_url: str | None = None
```

Build a read model over reminders plus watchlist jobs, and expose reminder-native mutations under `/api/v1/scheduled-tasks/reminders/...`.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Reminders/test_scheduled_tasks_control_plane.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/scheduled_tasks_control_plane_schemas.py tldw_Server_API/app/services/scheduled_tasks_control_plane_service.py tldw_Server_API/app/api/v1/endpoints/scheduled_tasks_control_plane.py tldw_Server_API/app/main.py tldw_Server_API/tests/Reminders/test_scheduled_tasks_control_plane.py
git commit -m "feat: add scheduled tasks control plane"
```

### Task 7: Add Shared Frontend Services For Integrations And Scheduled Tasks

**Files:**
- Create: `apps/packages/ui/src/services/integrations-control-plane.ts`
- Create: `apps/packages/ui/src/services/scheduled-tasks-control-plane.ts`
- Create: `apps/packages/ui/src/services/__tests__/integrations-control-plane.test.ts`
- Create: `apps/packages/ui/src/services/__tests__/scheduled-tasks-control-plane.test.ts`

**Step 1: Write the failing test**

```typescript
it("maps integrations control-plane responses into typed client objects", async () => {
  mockRequest({ items: [{ id: "slack:T123", provider: "slack", scope: "personal" }] })

  const result = await listPersonalIntegrations()
  expect(result.items[0].provider).toBe("slack")
})
```

**Step 2: Run test to verify it fails**

Run:

```bash
bun run --cwd apps/tldw-frontend test:run -- ../packages/ui/src/services/__tests__/integrations-control-plane.test.ts ../packages/ui/src/services/__tests__/scheduled-tasks-control-plane.test.ts
```

Expected: FAIL because the service modules do not exist yet.

**Step 3: Write minimal implementation**

```typescript
export async function listPersonalIntegrations() {
  return await bgRequest<IntegrationsListResponse>({ path: "/api/v1/integrations/personal", method: "GET" })
}
```

Add the scheduled-tasks list/detail and reminder mutation helpers in the same style.

**Step 4: Run test to verify it passes**

Run:

```bash
bun run --cwd apps/tldw-frontend test:run -- ../packages/ui/src/services/__tests__/integrations-control-plane.test.ts ../packages/ui/src/services/__tests__/scheduled-tasks-control-plane.test.ts
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/services/integrations-control-plane.ts apps/packages/ui/src/services/scheduled-tasks-control-plane.ts apps/packages/ui/src/services/__tests__/integrations-control-plane.test.ts apps/packages/ui/src/services/__tests__/scheduled-tasks-control-plane.test.ts
git commit -m "feat: add frontend control plane service clients"
```

### Task 8: Build The Shared Integrations UI

**Files:**
- Create: `apps/packages/ui/src/components/Option/Integrations/IntegrationManagementPage.tsx`
- Create: `apps/packages/ui/src/components/Option/Integrations/IntegrationProviderCard.tsx`
- Create: `apps/packages/ui/src/components/Option/Integrations/IntegrationConnectionDrawer.tsx`
- Create: `apps/packages/ui/src/components/Option/Integrations/IntegrationPolicyPanel.tsx`
- Create: `apps/packages/ui/src/components/Option/Integrations/__tests__/IntegrationManagementPage.test.tsx`
- Create: `apps/packages/ui/src/routes/option-integrations.tsx`
- Create: `apps/packages/ui/src/routes/option-admin-integrations.tsx`
- Create: `apps/packages/ui/src/routes/__tests__/integrations-route.test.tsx`
- Create: `apps/tldw-frontend/pages/integrations.tsx`
- Create: `apps/tldw-frontend/pages/admin/integrations.tsx`

**Step 1: Write the failing test**

```typescript
it("renders personal slack and discord cards and hides telegram", async () => {
  render(<IntegrationManagementPage scope="personal" />)
  expect(await screen.findByText("Slack")).toBeInTheDocument()
  expect(screen.getByText("Discord")).toBeInTheDocument()
  expect(screen.queryByText("Telegram")).not.toBeInTheDocument()
})
```

Add an admin-scope test that expects the Telegram section and policy controls.

**Step 2: Run test to verify it fails**

Run:

```bash
bun run --cwd apps/tldw-frontend test:run -- ../packages/ui/src/components/Option/Integrations/__tests__/IntegrationManagementPage.test.tsx ../packages/ui/src/routes/__tests__/integrations-route.test.tsx
```

Expected: FAIL because the components and routes do not exist yet.

**Step 3: Write minimal implementation**

```tsx
export function IntegrationManagementPage({ scope }: { scope: "personal" | "workspace" }) {
  const query = useQuery(...)
  return <div>{/* provider cards and drawers */}</div>
}
```

Use the normalized control-plane actions to drive button visibility instead of hard-coding provider behavior in the page.

**Step 4: Run test to verify it passes**

Run:

```bash
bun run --cwd apps/tldw-frontend test:run -- ../packages/ui/src/components/Option/Integrations/__tests__/IntegrationManagementPage.test.tsx ../packages/ui/src/routes/__tests__/integrations-route.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/Integrations apps/packages/ui/src/routes/option-integrations.tsx apps/packages/ui/src/routes/option-admin-integrations.tsx apps/packages/ui/src/routes/__tests__/integrations-route.test.tsx apps/tldw-frontend/pages/integrations.tsx apps/tldw-frontend/pages/admin/integrations.tsx
git commit -m "feat: add shared integrations management UI"
```

### Task 9: Build The Shared Scheduled Tasks UI

**Files:**
- Create: `apps/packages/ui/src/components/Option/ScheduledTasks/ScheduledTasksPage.tsx`
- Create: `apps/packages/ui/src/components/Option/ScheduledTasks/ScheduledTaskTable.tsx`
- Create: `apps/packages/ui/src/components/Option/ScheduledTasks/ReminderTaskEditor.tsx`
- Create: `apps/packages/ui/src/components/Option/ScheduledTasks/WatchlistJobReadOnlyPanel.tsx`
- Create: `apps/packages/ui/src/components/Option/ScheduledTasks/__tests__/ScheduledTasksPage.test.tsx`
- Create: `apps/packages/ui/src/routes/option-scheduled-tasks.tsx`
- Create: `apps/packages/ui/src/routes/__tests__/scheduled-tasks-route.test.tsx`
- Create: `apps/tldw-frontend/pages/scheduled-tasks.tsx`

**Step 1: Write the failing test**

```typescript
it("shows reminder rows as editable and watchlist rows as external-managed", async () => {
  render(<ScheduledTasksPage />)
  expect(await screen.findByText("Manage in Watchlists")).toBeInTheDocument()
  expect(screen.getByRole("button", { name: "Create Reminder Task" })).toBeInTheDocument()
})
```

**Step 2: Run test to verify it fails**

Run:

```bash
bun run --cwd apps/tldw-frontend test:run -- ../packages/ui/src/components/Option/ScheduledTasks/__tests__/ScheduledTasksPage.test.tsx ../packages/ui/src/routes/__tests__/scheduled-tasks-route.test.tsx
```

Expected: FAIL because the scheduled-tasks UI does not exist yet.

**Step 3: Write minimal implementation**

```tsx
export function ScheduledTasksPage() {
  const query = useQuery(...)
  return <div>{/* overview cards, reminder CRUD, watchlist deep links */}</div>
}
```

Make sure watchlist rows use `edit_mode === "external"` from the API contract instead of inference in the component.

**Step 4: Run test to verify it passes**

Run:

```bash
bun run --cwd apps/tldw-frontend test:run -- ../packages/ui/src/components/Option/ScheduledTasks/__tests__/ScheduledTasksPage.test.tsx ../packages/ui/src/routes/__tests__/scheduled-tasks-route.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/ScheduledTasks apps/packages/ui/src/routes/option-scheduled-tasks.tsx apps/packages/ui/src/routes/__tests__/scheduled-tasks-route.test.tsx apps/tldw-frontend/pages/scheduled-tasks.tsx
git commit -m "feat: add shared scheduled tasks management UI"
```

### Task 10: Wire Navigation, Extension Parity, And Verification

**Files:**
- Modify: `apps/packages/ui/src/routes/route-registry.tsx`
- Modify: `apps/packages/ui/src/components/Layouts/header-shortcut-items.ts`
- Create: `apps/extension/tests/e2e/integrations-and-scheduled-tasks.spec.ts`
- Modify: `Docs/Plans/2026-03-20-integrations-and-scheduled-tasks-control-plane-design.md`

**Step 1: Write the failing test**

```typescript
it("registers integrations and scheduled tasks in the route registry", () => {
  const paths = getAllOptionRoutes().map((route) => route.path)
  expect(paths).toContain("/integrations")
  expect(paths).toContain("/scheduled-tasks")
  expect(paths).toContain("/admin/integrations")
})
```

Add the extension parity smoke test that visits both new pages.

**Step 2: Run test to verify it fails**

Run:

```bash
bun run --cwd apps/tldw-frontend test:run -- ../packages/ui/src/routes/__tests__/integrations-route.test.tsx ../packages/ui/src/routes/__tests__/scheduled-tasks-route.test.tsx
bun run --cwd apps/extension compile
```

Expected: route-registry test fails before wiring; extension compile passes only after imports/routes are consistent.

**Step 3: Write minimal implementation**

```tsx
{ kind: "options", path: "/integrations", element: <OptionIntegrations />, nav: { ... } }
{ kind: "options", path: "/scheduled-tasks", element: <OptionScheduledTasks />, nav: { ... } }
{ kind: "options", path: "/admin/integrations", element: <OptionAdminIntegrations /> }
```

Also update the design doc if final implementation decisions differ in a meaningful way during execution.

**Step 4: Run test to verify it passes**

Run:

```bash
bun run --cwd apps/tldw-frontend test:run -- ../packages/ui/src/routes/__tests__/integrations-route.test.tsx ../packages/ui/src/routes/__tests__/scheduled-tasks-route.test.tsx
bun run --cwd apps/extension compile
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Integrations tldw_Server_API/tests/Telegram/test_telegram_admin_link_inventory.py tldw_Server_API/tests/Reminders/test_scheduled_tasks_control_plane.py -v
source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/endpoints/integrations_control_plane.py tldw_Server_API/app/api/v1/endpoints/scheduled_tasks_control_plane.py tldw_Server_API/app/services/integrations_control_plane_service.py tldw_Server_API/app/services/scheduled_tasks_control_plane_service.py tldw_Server_API/app/core/AuthNZ/repos/workspace_provider_installations_repo.py -f json -o /tmp/bandit_integrations_scheduled_tasks_control_plane.json
```

Expected:

- frontend route tests PASS
- extension compile PASS
- targeted backend suites PASS
- Bandit produces a report with no new findings in touched code

**Step 5: Commit**

```bash
git add apps/packages/ui/src/routes/route-registry.tsx apps/packages/ui/src/components/Layouts/header-shortcut-items.ts apps/extension/tests/e2e/integrations-and-scheduled-tasks.spec.ts Docs/Plans/2026-03-20-integrations-and-scheduled-tasks-control-plane-design.md
git commit -m "feat: wire integrations and scheduled tasks management routes"
```

## Execution Notes

- Follow @test-driven-development for each task.
- Use @verification-before-completion before claiming the feature is complete.
- Do not let the frontend talk to the legacy Slack/Discord/Telegram management endpoints directly once the control plane exists.
- Keep `/connectors` separate from `/integrations`; do not fold messaging integrations into the content-sync connector IA.
- Preserve watchlist jobs as `external`-managed in the unified scheduled-tasks contract.
- Record installer ownership and audit metadata whenever admins disable or remove workspace installations.

## Suggested Verification Sequence

1. Backend registry repo + callback persistence tests
2. Telegram admin inventory/revoke tests
3. Integrations control-plane endpoint tests
4. Scheduled-tasks control-plane tests
5. Frontend service tests
6. Shared UI route/component tests
7. Extension compile
8. Bandit

## Handoff Reminder

The design doc for this plan is saved at:

- `Docs/Plans/2026-03-20-integrations-and-scheduled-tasks-control-plane-design.md`

The implementation must stay consistent with these approved constraints:

- personal page: Slack and Discord only
- workspace page: Slack, Discord, Telegram
- Telegram admin scope requires linked-actor inventory and revoke
- watchlist jobs are visible in `/scheduled-tasks` but managed in `/watchlists`
