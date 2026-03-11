# MCP Hub Tool Permissions Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build MCP Hub into the canonical editor and runtime source of truth for tool permissions, approvals, and tool-related credentials, while keeping persona and agent UIs focused on non-tool configuration.

**Architecture:** Extend the existing MCP Hub backend into a durable policy domain with profiles, assignments, overrides, approval policies, and credential bindings; then add a policy resolver and approval service that the MCP protocol can call before tool execution. On the frontend, replace the current ACP-oriented MCP Hub tabs with governance-first tabs and surface only effective policy summaries inside persona and agent screens.

**Tech Stack:** FastAPI, Pydantic, SQLite/PostgreSQL migrations, existing AuthNZ RBAC, MCP Unified protocol layer, React, Ant Design, existing `bgRequestClient` service client, pytest, Vitest, Bandit.

---

Use @superpowers:test-driven-development for each task, @superpowers:systematic-debugging if a test fails unexpectedly, and @superpowers:verification-before-completion before claiming the work is done. Prefer implementation in a dedicated worktree.

### Task 1: Add Durable MCP Hub Policy Storage

**Files:**
- Modify: `tldw_Server_API/app/core/AuthNZ/migrations.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py`
- Test: `tldw_Server_API/tests/AuthNZ_SQLite/test_mcp_hub_migrations.py`
- Test: `tldw_Server_API/tests/AuthNZ_Postgres/test_mcp_hub_pg_ensure.py`
- Test: `tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_repo.py`

**Step 1: Write the failing migration and repo tests**

```python
async def test_mcp_hub_repo_creates_and_lists_policy_assignment(sqlite_pool):
    repo = McpHubRepo(sqlite_pool)
    await repo.ensure_tables()

    created = await repo.create_policy_assignment(
        target_type="default",
        target_id=None,
        owner_scope_type="user",
        owner_scope_id=7,
        profile_id=None,
        inline_policy_document={"capabilities": ["filesystem.read"]},
        approval_policy_id=None,
        actor_id=7,
    )

    rows = await repo.list_policy_assignments(owner_scope_type="user", owner_scope_id=7)
    assert created["target_type"] == "default"
    assert rows[0]["inline_policy_document"]["capabilities"] == ["filesystem.read"]
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ_SQLite/test_mcp_hub_migrations.py tldw_Server_API/tests/AuthNZ_Postgres/test_mcp_hub_pg_ensure.py tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_repo.py -v`

Expected: FAIL with missing tables, missing schema classes, or missing repo methods for policy assignments, approval policies, overrides, and credential bindings.

**Step 3: Write the minimal implementation**

```python
class PolicyAssignmentCreateRequest(BaseModel):
    target_type: Literal["default", "group", "persona"]
    target_id: str | None = None
    owner_scope_type: ScopeType = "global"
    owner_scope_id: int | None = None
    profile_id: int | None = None
    inline_policy_document: dict[str, Any] = Field(default_factory=dict)
    approval_policy_id: int | None = None
    is_active: bool = True
```

```python
async def create_policy_assignment(self, *, target_type: str, target_id: str | None, owner_scope_type: str, owner_scope_id: int | None, profile_id: int | None, inline_policy_document: dict[str, Any], approval_policy_id: int | None, actor_id: int | None) -> dict[str, Any]:
    ...
```

Add durable tables for:

- `mcp_permission_profiles`
- `mcp_policy_assignments`
- `mcp_policy_overrides`
- `mcp_approval_policies`
- `mcp_approval_decisions`
- `mcp_credential_bindings`
- `mcp_policy_audit_history`

Keep current `mcp_acp_profiles` and external server tables intact during migration.

**Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ_SQLite/test_mcp_hub_migrations.py tldw_Server_API/tests/AuthNZ_Postgres/test_mcp_hub_pg_ensure.py tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_repo.py -v`

Expected: PASS for new table creation and basic CRUD coverage.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/AuthNZ/migrations.py tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py tldw_Server_API/tests/AuthNZ_SQLite/test_mcp_hub_migrations.py tldw_Server_API/tests/AuthNZ_Postgres/test_mcp_hub_pg_ensure.py tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_repo.py
git commit -m "feat: add MCP Hub policy storage"
```

### Task 2: Add MCP Hub Policy Service And API

**Files:**
- Modify: `tldw_Server_API/app/services/mcp_hub_service.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py`
- Test: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py`
- Create: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py`
- Test: `tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_permissions_claims.py`

**Step 1: Write the failing API tests**

```python
def test_create_policy_assignment_requires_grant_authority(client, auth_headers):
    response = client.post(
        "/api/v1/mcp/hub/policy-assignments",
        json={
            "target_type": "persona",
            "target_id": "researcher",
            "owner_scope_type": "user",
            "owner_scope_id": 7,
            "inline_policy_document": {"capabilities": ["process.execute"]},
        },
        headers=auth_headers,
    )
    assert response.status_code == 403
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_permissions_claims.py -v`

Expected: FAIL because the routes, grant-authority checks, and response models do not exist yet.

**Step 3: Write the minimal implementation**

```python
@router.post("/policy-assignments", response_model=PolicyAssignmentResponse, status_code=201)
async def create_policy_assignment(...):
    _require_mcp_hub_mutation_permission(principal)
    await svc.assert_grant_authority(
        principal=principal,
        proposed_policy=payload.inline_policy_document,
        inherited_policy=payload.inherited_policy_document,
    )
    row = await svc.create_policy_assignment(...)
    return _assignment_row_to_response(row)
```

```python
async def assert_grant_authority(self, *, principal: AuthPrincipal, proposed_policy: dict[str, Any], inherited_policy: dict[str, Any]) -> None:
    broadened = diff_broadened_capabilities(inherited_policy, proposed_policy)
    if broadened and not principal_can_grant(principal, broadened):
        raise HTTPException(status_code=403, detail="Grant authority required")
```

Add CRUD endpoints for:

- permission profiles
- policy assignments
- policy overrides
- approval policies
- credential bindings

**Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_permissions_claims.py -v`

Expected: PASS with coverage for create, list, update, delete, and unauthorized broadening attempts.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/services/mcp_hub_service.py tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_permissions_claims.py
git commit -m "feat: add MCP Hub policy management API"
```

### Task 3: Add Tool Capability Registry And Effective Policy Resolver

**Files:**
- Create: `tldw_Server_API/app/core/MCP_unified/tool_capability_registry.py`
- Create: `tldw_Server_API/app/core/MCP_unified/policy_resolver.py`
- Modify: `tldw_Server_API/app/core/MCP_unified/protocol.py`
- Modify: `tldw_Server_API/app/core/MCP_unified/modules/implementations/external_federation_module.py`
- Test: `tldw_Server_API/app/core/MCP_unified/tests/test_protocol_scope_enforcement.py`
- Create: `tldw_Server_API/app/core/MCP_unified/tests/test_policy_resolver.py`
- Test: `tldw_Server_API/app/core/MCP_unified/tests/test_external_federation_integration.py`

**Step 1: Write the failing resolver tests**

```python
async def test_policy_resolver_merges_default_group_and_persona_assignments():
    resolver = McpPolicyResolver(repo=FakeRepo(), capability_registry=FakeRegistry())
    result = await resolver.resolve(
        user_id="7",
        group_ids=["writers"],
        persona_id="researcher",
        tool_name="files.read_text",
        arguments={"path": "/workspace/doc.txt"},
    )
    assert result.allowed is True
    assert result.requires_approval is False
    assert "filesystem.read" in result.capabilities
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/app/core/MCP_unified/tests/test_policy_resolver.py tldw_Server_API/app/core/MCP_unified/tests/test_protocol_scope_enforcement.py tldw_Server_API/app/core/MCP_unified/tests/test_external_federation_integration.py -v`

Expected: FAIL because there is no capability registry or resolver yet, and the protocol cannot consume effective policy.

**Step 3: Write the minimal implementation**

```python
@dataclass
class EffectiveToolPolicy:
    allowed: bool
    requires_approval: bool
    capabilities: set[str]
    deny_reason: str | None
    provenance: list[str]
```

```python
class McpPolicyResolver:
    async def resolve(self, *, user_id: str, group_ids: list[str], persona_id: str | None, tool_name: str, arguments: dict[str, Any]) -> EffectiveToolPolicy:
        tool_meta = self.capability_registry.get(tool_name)
        assignments = await self.repo.list_runtime_assignments(user_id=user_id, group_ids=group_ids, persona_id=persona_id)
        merged = merge_assignments(assignments, tool_meta, arguments)
        return to_effective_policy(merged, tool_meta)
```

Wire `protocol.py` so `_has_tool_permission` becomes a layered check:

1. existing RBAC and API key ceilings
2. resolver-based effective policy
3. approval requirement trigger

**Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/app/core/MCP_unified/tests/test_policy_resolver.py tldw_Server_API/app/core/MCP_unified/tests/test_protocol_scope_enforcement.py tldw_Server_API/app/core/MCP_unified/tests/test_external_federation_integration.py -v`

Expected: PASS with resolver merge coverage and protocol enforcement coverage.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/MCP_unified/tool_capability_registry.py tldw_Server_API/app/core/MCP_unified/policy_resolver.py tldw_Server_API/app/core/MCP_unified/protocol.py tldw_Server_API/app/core/MCP_unified/modules/implementations/external_federation_module.py tldw_Server_API/app/core/MCP_unified/tests/test_policy_resolver.py tldw_Server_API/app/core/MCP_unified/tests/test_protocol_scope_enforcement.py tldw_Server_API/app/core/MCP_unified/tests/test_external_federation_integration.py
git commit -m "feat: resolve effective MCP tool policy"
```

### Task 4: Add Runtime Approval Service And Migration Boundaries

**Files:**
- Create: `tldw_Server_API/app/core/MCP_unified/approval_service.py`
- Modify: `tldw_Server_API/app/core/MCP_unified/protocol.py`
- Modify: `tldw_Server_API/app/core/MCP_unified/external_servers/config_schema.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_service.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/persona.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/persona.py`
- Test: `tldw_Server_API/app/core/MCP_unified/tests/test_protocol_governance_preflight.py`
- Create: `tldw_Server_API/app/core/MCP_unified/tests/test_approval_service.py`
- Test: `tldw_Server_API/tests/Persona/test_persona_profiles_api.py`

**Step 1: Write the failing approval and compatibility tests**

```python
async def test_temporary_elevation_is_scoped_to_conversation_and_expires():
    service = ApprovalService(repo=FakeRepo(), clock=FakeClock())
    token = await service.approve(
        user_id="7",
        context_key="persona:researcher",
        conversation_id="conv-1",
        tool_name="process.exec",
        scope_key="risk:process.execute",
        ttl_seconds=60,
    )
    assert await service.allows(token, conversation_id="conv-1") is True
    assert await service.allows(token, conversation_id="conv-2") is False
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/app/core/MCP_unified/tests/test_protocol_governance_preflight.py tldw_Server_API/app/core/MCP_unified/tests/test_approval_service.py tldw_Server_API/tests/Persona/test_persona_profiles_api.py -v`

Expected: FAIL because there is no approval service, no scoped elevation handling, and no persona-facing effective policy summary.

**Step 3: Write the minimal implementation**

```python
class ApprovalService:
    async def approve(self, *, user_id: str, context_key: str, conversation_id: str | None, tool_name: str, scope_key: str, ttl_seconds: int) -> ApprovalDecision:
        ...

    async def allows(self, decision: ApprovalDecision, *, conversation_id: str | None) -> bool:
        ...
```

```python
class PersonaToolPolicySummary(BaseModel):
    persona_id: str
    assignment_target: str
    profile_name: str | None = None
    approval_mode: str | None = None
    effective_capabilities: list[str] = Field(default_factory=list)
```

Implement:

- approval tokens keyed by user, target context, session or conversation, tool or risk class, and TTL
- persona summary endpoint backed by MCP Hub state
- explicit migration rule for external server definitions and persona tool-policy compatibility

**Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/app/core/MCP_unified/tests/test_protocol_governance_preflight.py tldw_Server_API/app/core/MCP_unified/tests/test_approval_service.py tldw_Server_API/tests/Persona/test_persona_profiles_api.py -v`

Expected: PASS with approval TTL, scoped elevation, and persona summary coverage.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/MCP_unified/approval_service.py tldw_Server_API/app/core/MCP_unified/protocol.py tldw_Server_API/app/core/MCP_unified/external_servers/config_schema.py tldw_Server_API/app/services/mcp_hub_service.py tldw_Server_API/app/api/v1/endpoints/persona.py tldw_Server_API/app/api/v1/schemas/persona.py tldw_Server_API/app/core/MCP_unified/tests/test_protocol_governance_preflight.py tldw_Server_API/app/core/MCP_unified/tests/test_approval_service.py tldw_Server_API/tests/Persona/test_persona_profiles_api.py
git commit -m "feat: add MCP approval flow and persona summary"
```

### Task 5: Replace MCP Hub Frontend With Governance Tabs

**Files:**
- Modify: `apps/packages/ui/src/components/Option/MCPHub/McpHubPage.tsx`
- Create: `apps/packages/ui/src/components/Option/MCPHub/ProfilesTab.tsx`
- Create: `apps/packages/ui/src/components/Option/MCPHub/AssignmentsTab.tsx`
- Create: `apps/packages/ui/src/components/Option/MCPHub/ApprovalsTab.tsx`
- Create: `apps/packages/ui/src/components/Option/MCPHub/CredentialsTab.tsx`
- Create: `apps/packages/ui/src/components/Option/MCPHub/EffectivePolicyPreview.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/index.tsx`
- Modify: `apps/packages/ui/src/services/tldw/mcp-hub.ts`
- Create: `apps/packages/ui/src/components/Option/MCPHub/__tests__/ProfilesTab.test.tsx`
- Create: `apps/packages/ui/src/components/Option/MCPHub/__tests__/AssignmentsTab.test.tsx`
- Create: `apps/packages/ui/src/components/Option/MCPHub/__tests__/ApprovalsTab.test.tsx`
- Create: `apps/packages/ui/src/components/Option/MCPHub/__tests__/CredentialsTab.test.tsx`
- Modify: `apps/packages/ui/src/services/tldw/__tests__/mcp-hub.test.ts`

**Step 1: Write the failing UI and service tests**

```tsx
it("shows effective policy provenance for a persona assignment", async () => {
  render(<AssignmentsTab />)
  expect(await screen.findByText(/granted by profile/i)).toBeInTheDocument()
  expect(screen.getByText(/approval required because/i)).toBeInTheDocument()
})
```

**Step 2: Run tests to verify they fail**

Run: `bunx vitest run apps/packages/ui/src/components/Option/MCPHub/__tests__/ProfilesTab.test.tsx apps/packages/ui/src/components/Option/MCPHub/__tests__/AssignmentsTab.test.tsx apps/packages/ui/src/components/Option/MCPHub/__tests__/ApprovalsTab.test.tsx apps/packages/ui/src/components/Option/MCPHub/__tests__/CredentialsTab.test.tsx apps/packages/ui/src/services/tldw/__tests__/mcp-hub.test.ts`

Expected: FAIL because the new tabs, provenance preview, and expanded service client do not exist yet.

**Step 3: Write the minimal implementation**

```tsx
export const McpHubPage = () => {
  const [activeTab, setActiveTab] = useState("profiles")
  return (
    <Tabs
      activeKey={activeTab}
      onChange={setActiveTab}
      items={[
        { key: "profiles", label: "Profiles", children: <ProfilesTab /> },
        { key: "assignments", label: "Assignments", children: <AssignmentsTab /> },
        { key: "approvals", label: "Approvals", children: <ApprovalsTab /> },
        { key: "credentials", label: "Credentials", children: <CredentialsTab /> },
        { key: "catalog", label: "Catalog", children: <ToolCatalogsTab /> },
      ]}
    />
  )
}
```

```ts
export type McpHubPolicyAssignment = {
  id: number
  target_type: "default" | "group" | "persona"
  target_id?: string | null
  profile_id?: number | null
  inline_policy_document: Record<string, unknown>
  approval_policy_id?: number | null
}
```

Implement:

- simple and advanced profile editing
- assignment flow for `default`, `group`, and `persona`
- effective-policy preview with provenance and approval reason strings
- credential management using MCP Hub APIs, not persona-local storage

**Step 4: Run tests to verify they pass**

Run: `bunx vitest run apps/packages/ui/src/components/Option/MCPHub/__tests__/ProfilesTab.test.tsx apps/packages/ui/src/components/Option/MCPHub/__tests__/AssignmentsTab.test.tsx apps/packages/ui/src/components/Option/MCPHub/__tests__/ApprovalsTab.test.tsx apps/packages/ui/src/components/Option/MCPHub/__tests__/CredentialsTab.test.tsx apps/packages/ui/src/services/tldw/__tests__/mcp-hub.test.ts`

Expected: PASS with tab rendering, API calls, and effective-preview behavior covered.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/MCPHub/McpHubPage.tsx apps/packages/ui/src/components/Option/MCPHub/ProfilesTab.tsx apps/packages/ui/src/components/Option/MCPHub/AssignmentsTab.tsx apps/packages/ui/src/components/Option/MCPHub/ApprovalsTab.tsx apps/packages/ui/src/components/Option/MCPHub/CredentialsTab.tsx apps/packages/ui/src/components/Option/MCPHub/EffectivePolicyPreview.tsx apps/packages/ui/src/components/Option/MCPHub/index.tsx apps/packages/ui/src/services/tldw/mcp-hub.ts apps/packages/ui/src/components/Option/MCPHub/__tests__/ProfilesTab.test.tsx apps/packages/ui/src/components/Option/MCPHub/__tests__/AssignmentsTab.test.tsx apps/packages/ui/src/components/Option/MCPHub/__tests__/ApprovalsTab.test.tsx apps/packages/ui/src/components/Option/MCPHub/__tests__/CredentialsTab.test.tsx apps/packages/ui/src/services/tldw/__tests__/mcp-hub.test.ts
git commit -m "feat: rebuild MCP Hub governance UI"
```

### Task 6: Add Persona UI Summary, Documentation, And Final Verification

**Files:**
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- Modify: `apps/packages/ui/src/services/tldw/mcp-hub.ts`
- Create: `apps/packages/ui/src/routes/__tests__/mcp-hub-route.test.tsx`
- Test: `tldw_Server_API/tests/Persona/test_persona_catalog.py`
- Modify: `Docs/MCP/mcp_hub_management.md`
- Modify: `README.md`

**Step 1: Write the failing summary and docs tests**

```tsx
it("shows the linked MCP Hub policy summary and edit link", async () => {
  render(<SidepanelPersona />)
  expect(await screen.findByText(/effective tool access/i)).toBeInTheDocument()
  expect(screen.getByRole("link", { name: /open in MCP Hub/i })).toBeInTheDocument()
})
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_catalog.py -v && bunx vitest run apps/packages/ui/src/routes/__tests__/mcp-hub-route.test.tsx`

Expected: FAIL because persona UI does not show MCP Hub-linked effective tool access yet.

**Step 3: Write the minimal implementation**

```tsx
<Card title="Effective Tool Access">
  <p>{summary.profile_name ?? "Manual configuration"}</p>
  <p>{summary.approval_mode ?? "No approval policy"}</p>
  <Link to="/settings/mcp-hub">Open in MCP Hub</Link>
</Card>
```

Update docs to explain:

- how profiles, assignments, overrides, and approvals interact
- how persona UI consumes MCP Hub state
- how external server config migration works

**Step 4: Run full targeted verification and security scan**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py tldw_Server_API/app/core/MCP_unified/tests/test_policy_resolver.py tldw_Server_API/app/core/MCP_unified/tests/test_approval_service.py tldw_Server_API/tests/Persona/test_persona_profiles_api.py tldw_Server_API/tests/Persona/test_persona_catalog.py -v`

Run: `bunx vitest run apps/packages/ui/src/components/Option/MCPHub/__tests__/ProfilesTab.test.tsx apps/packages/ui/src/components/Option/MCPHub/__tests__/AssignmentsTab.test.tsx apps/packages/ui/src/components/Option/MCPHub/__tests__/ApprovalsTab.test.tsx apps/packages/ui/src/components/Option/MCPHub/__tests__/CredentialsTab.test.tsx apps/packages/ui/src/routes/__tests__/mcp-hub-route.test.tsx apps/packages/ui/src/services/tldw/__tests__/mcp-hub.test.ts`

Run: `source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py tldw_Server_API/app/services/mcp_hub_service.py tldw_Server_API/app/core/MCP_unified tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py -f json -o /tmp/bandit_mcp_hub_policy.json`

Expected: PASS for tests; Bandit report contains no new high-confidence findings in touched code.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/services/tldw/mcp-hub.ts apps/packages/ui/src/routes/__tests__/mcp-hub-route.test.tsx tldw_Server_API/tests/Persona/test_persona_catalog.py Docs/MCP/mcp_hub_management.md README.md
git commit -m "docs: document MCP Hub tool permissions flow"
```
