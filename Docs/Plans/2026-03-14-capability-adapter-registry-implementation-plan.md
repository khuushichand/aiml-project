# Capability Adapter Registry Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add scope-aware capability adapter mappings to MCP Hub and make them the canonical capability-resolution layer for governance-pack dry-run/import, effective-policy assembly, and runtime enforcement at the policy-resolver boundary.

**Architecture:** Introduce a persisted MCP Hub capability-mapping domain for `global`, `org`, and `team` scopes, validate mapping outputs against the tool registry and grant-authority rules, and resolve capabilities at effective-policy read time rather than materializing permanent expansions into every policy object. Keep direct concrete tool fields fully editable as peer inputs, return both authored and resolved policy documents, and route governance-pack dry-run/import through the same resolution service used by runtime policy resolution.

**Tech Stack:** FastAPI, Pydantic, SQLite/PostgreSQL AuthNZ migrations, MCP Hub repo/services, React, Vitest, pytest, Bandit

---

## Status

- Task 1: Complete
- Task 2: Complete
- Task 3: Complete
- Task 4: Complete
- Task 5: Complete
- Task 6: In Progress

### Task 1: Add capability-mapping storage and repo coverage

**Files:**
- Modify: `tldw_Server_API/app/core/AuthNZ/migrations.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py`
- Create: `tldw_Server_API/tests/AuthNZ_SQLite/test_mcp_hub_capability_adapter_migrations.py`
- Modify: `tldw_Server_API/tests/AuthNZ_Postgres/test_mcp_hub_pg_ensure.py`

**Step 1: Write the failing storage tests**

Add tests that expect:

- a new `mcp_capability_adapter_mappings` table exists in SQLite and PostgreSQL ensure flows
- rows store `mapping_id`, scope ownership, `capability_name`, `adapter_contract_version`, `resolved_policy_document_json`, `supported_environment_requirements_json`, and `is_active`
- duplicate active mappings for the same `(owner_scope_type, owner_scope_id, capability_name)` are rejected

Example test shape:

```python
async def test_create_capability_mapping_rejects_duplicate_active_scope_capability(repo):
    await repo.create_capability_adapter_mapping(
        mapping_id="research.global",
        owner_scope_type="global",
        owner_scope_id=None,
        capability_name="tool.invoke.research",
        adapter_contract_version=1,
        resolved_policy_document={"allowed_tools": ["web.search"]},
        supported_environment_requirements=["local_mapping_required"],
        is_active=True,
    )

    with pytest.raises(Exception):
        await repo.create_capability_adapter_mapping(
            mapping_id="research.global.duplicate",
            owner_scope_type="global",
            owner_scope_id=None,
            capability_name="tool.invoke.research",
            adapter_contract_version=1,
            resolved_policy_document={"allowed_tools": ["docs.search"]},
            supported_environment_requirements=[],
            is_active=True,
        )
```

**Step 2: Run the focused tests to confirm they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/AuthNZ_SQLite/test_mcp_hub_capability_adapter_migrations.py \
  tldw_Server_API/tests/AuthNZ_Postgres/test_mcp_hub_pg_ensure.py -v
```

Expected: FAIL because the table and repo methods do not exist yet.

**Step 3: Add the migration and repo support**

Implement:

- SQLite migration for `mcp_capability_adapter_mappings`
- PostgreSQL ensure statements for the same table
- repo methods:
  - `create_capability_adapter_mapping`
  - `get_capability_adapter_mapping`
  - `list_capability_adapter_mappings`
  - `update_capability_adapter_mapping`
  - `delete_capability_adapter_mapping`
  - `find_active_capability_mapping`

Use a uniqueness rule that blocks multiple active mappings for the same scope/capability. Keep inactive rows allowed for audit/history.

**Step 4: Re-run the focused tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/AuthNZ_SQLite/test_mcp_hub_capability_adapter_migrations.py \
  tldw_Server_API/tests/AuthNZ_Postgres/test_mcp_hub_pg_ensure.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/core/AuthNZ/migrations.py \
  tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py \
  tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py \
  tldw_Server_API/tests/AuthNZ_SQLite/test_mcp_hub_capability_adapter_migrations.py \
  tldw_Server_API/tests/AuthNZ_Postgres/test_mcp_hub_pg_ensure.py
git commit -m "feat: add MCP Hub capability adapter storage"
```

### Task 2: Add capability-mapping validation, preview, and CRUD APIs

**Files:**
- Create: `tldw_Server_API/app/services/mcp_hub_capability_adapter_service.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py`
- Create: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_capability_adapter_api.py`
- Create: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_capability_adapter_service.py`

**Step 1: Write the failing service and API tests**

Add tests that expect:

- create/list/update/delete endpoints for capability mappings
- mapping preview returns normalized resolved effects, warnings, and affected-scope summary
- unsupported `adapter_contract_version` is rejected
- unknown tool names or modules are rejected using the MCP tool registry
- principals without the necessary `grant.*` permissions cannot create a mapping whose resolved policy grants those effects

Example service test:

```python
async def test_preview_mapping_rejects_unknown_tools(service):
    with pytest.raises(BadRequestError, match="unknown tool"):
        await service.preview_mapping(
            owner_scope_type="global",
            owner_scope_id=None,
            capability_name="tool.invoke.research",
            adapter_contract_version=1,
            resolved_policy_document={"allowed_tools": ["missing.tool"]},
            supported_environment_requirements=[],
        )
```

**Step 2: Run the focused tests to confirm they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_capability_adapter_service.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_capability_adapter_api.py -v
```

Expected: FAIL because the service, schemas, and routes do not exist yet.

**Step 3: Implement the service and API layer**

Add request/response schemas such as:

- `CapabilityAdapterMappingCreateRequest`
- `CapabilityAdapterMappingUpdateRequest`
- `CapabilityAdapterMappingResponse`
- `CapabilityAdapterMappingPreviewRequest`
- `CapabilityAdapterMappingPreviewResponse`

Implement service behaviors:

- validate scope ownership
- allow only `adapter_contract_version == 1`
- validate resolved policy against the MCP tool registry
- call the existing grant-authority logic against the mapping's concrete resolved effects
- return preview warnings for unresolved environment requirements

Add endpoints under `/api/v1/mcp/hub/capability-mappings`.

**Step 4: Re-run the focused tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_capability_adapter_service.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_capability_adapter_api.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/services/mcp_hub_capability_adapter_service.py \
  tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py \
  tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_capability_adapter_service.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_capability_adapter_api.py
git commit -m "feat: add capability adapter mapping APIs"
```

### Task 3: Add the scope-aware capability resolution service

**Files:**
- Create: `tldw_Server_API/app/services/mcp_hub_capability_resolution_service.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py`
- Create: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_capability_resolution.py`

**Step 1: Write the failing resolution tests**

Add tests that expect:

- `team` mapping overrides `org`, which overrides `global`
- user-scoped runtime context still resolves through `team -> org -> global`
- unresolved capabilities produce no grants and explicit diagnostics
- resolved mapping effects are deduped before being returned
- supported environment requirements are tracked separately from unsupported ones

Example test shape:

```python
async def test_resolution_prefers_team_mapping_over_org_and_global(service):
    result = await service.resolve_capabilities(
        capability_names=["tool.invoke.research"],
        metadata={"team_id": 9, "org_id": 4},
    )
    assert result.resolved_capabilities == ["tool.invoke.research"]
    assert result.resolved_policy_document["allowed_tools"] == ["team.search"]
    assert result.mapping_summaries[0]["mapping_scope_type"] == "team"
```

**Step 2: Run the focused tests to confirm they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_capability_resolution.py -v
```

Expected: FAIL because the resolution service does not exist yet.

**Step 3: Implement the minimal resolution service**

Implement:

- a result model with:
  - `resolved_capabilities`
  - `unresolved_capabilities`
  - `resolved_policy_document`
  - `mapping_summaries`
  - `warnings`
- scope search order `team -> org -> global`
- list-field union semantics for resolved concrete effects
- dedupe for tool entries

Do not apply path/approval runtime narrowing here. This service resolves mappings only.

**Step 4: Re-run the focused tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_capability_resolution.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/services/mcp_hub_capability_resolution_service.py \
  tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_capability_resolution.py
git commit -m "feat: add scope-aware capability resolution"
```

### Task 4: Integrate capability resolution into the policy resolver and effective-policy schema

**Files:**
- Modify: `tldw_Server_API/app/services/mcp_hub_policy_resolver.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_resolver.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_overrides.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_shared_workspace_registry.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_workspace_set_objects.py`

**Step 1: Write the failing resolver tests**

Add tests that expect:

- effective-policy returns both `authored_policy_document` and `resolved_policy_document`
- direct concrete list fields are union-merged with mapping outputs
- direct scalar knobs win over mapping hints
- mapping provenance is present
- unresolved capabilities remain visible without granting concrete tools

Example test shape:

```python
async def test_effective_policy_merges_direct_tools_with_resolved_mapping():
    result = await resolver.resolve_for_context(
        user_id=7,
        metadata={"mcp_policy_context_enabled": True, "org_id": 4},
    )
    assert result["authored_policy_document"]["capabilities"] == ["tool.invoke.research"]
    assert sorted(result["allowed_tools"]) == ["direct.tool", "mapped.tool"]
    assert result["resolved_policy_document"]["allowed_tools"] == ["direct.tool", "mapped.tool"]
```

**Step 2: Run the focused tests to confirm they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_resolver.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_overrides.py -v
```

Expected: FAIL because the resolver and schema do not expose authored/resolved policy splits or mapping provenance yet.

**Step 3: Update the resolver and schemas**

Modify the resolver so it:

- builds `authored_policy_document` from the existing merge path
- resolves authored capabilities through `McpHubCapabilityResolutionService`
- creates `resolved_policy_document`
- keeps top-level `allowed_tools`, `denied_tools`, and `capabilities` derived from the resolved form
- appends new provenance kinds:
  - `capability_mapping`
  - `runtime_constraint` (placeholder-ready, even if some callers only use mapping provenance in this task)

Update the Pydantic and frontend-facing response schema shapes accordingly.

**Step 4: Re-run the focused tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_resolver.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_overrides.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_shared_workspace_registry.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_workspace_set_objects.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/services/mcp_hub_policy_resolver.py \
  tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_resolver.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_overrides.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_shared_workspace_registry.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_workspace_set_objects.py
git commit -m "feat: resolve capabilities in effective policy"
```

### Task 5: Switch governance-pack dry-run/import to the registry-backed resolver

**Files:**
- Modify: `tldw_Server_API/app/services/mcp_hub_governance_pack_service.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_api.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_import.py`

**Step 1: Write the failing governance-pack tests**

Add tests that expect:

- dry-run uses live adapter mappings instead of the hardcoded capability set
- a pack with no applicable mapping reports unresolved capabilities and `blocked`
- the same pack becomes `importable` after creating the right scope-aware mapping
- dry-run includes mapping summaries and stricter-local warnings

Example test shape:

```python
async def test_governance_pack_dry_run_uses_live_capability_mapping(service, mapping_repo):
    pack = load_governance_pack_fixture("minimal_researcher_pack")
    report = await service.dry_run_pack(pack=pack, owner_scope_type="global", owner_scope_id=None)
    assert report.verdict == "blocked"

    await mapping_repo.create_capability_adapter_mapping(
        mapping_id="research.global",
        owner_scope_type="global",
        owner_scope_id=None,
        capability_name="tool.invoke.research",
        adapter_contract_version=1,
        resolved_policy_document={"allowed_tools": ["web.search"]},
        supported_environment_requirements=["workspace_bounded_read"],
        is_active=True,
    )

    report = await service.dry_run_pack(pack=pack, owner_scope_type="global", owner_scope_id=None)
    assert report.verdict == "importable"
    assert report.resolved_capabilities == ["filesystem.read", "tool.invoke.research"]
```

**Step 2: Run the focused tests to confirm they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_api.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_import.py -v
```

Expected: FAIL because dry-run/import still use hardcoded capability support.

**Step 3: Replace hardcoded dry-run logic**

Implement:

- inject the capability-resolution service into governance-pack dry-run/import
- replace `_SUPPORTED_PORTABLE_CAPABILITIES` checks with live resolution output
- keep approval-template mapping validation, but move capability support decisions to the registry-backed resolver
- include mapping summaries and unresolved capability diagnostics in the response model

**Step 4: Re-run the focused tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_api.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_import.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/services/mcp_hub_governance_pack_service.py \
  tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_api.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_import.py
git commit -m "feat: route governance pack dry-runs through capability mappings"
```

### Task 6: Add MCP Hub UI for capability mappings and resolved-policy visibility

**Files:**
- Create: `apps/packages/ui/src/components/Option/MCPHub/CapabilityMappingsTab.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/McpHubPage.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/index.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/PersonaPolicySummary.tsx`
- Modify: `apps/packages/ui/src/services/tldw/mcp-hub.ts`
- Create: `apps/packages/ui/src/components/Option/MCPHub/__tests__/CapabilityMappingsTab.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/McpHubPage.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/PersonaPolicySummary.test.tsx`
- Modify: `apps/packages/ui/src/services/tldw/__tests__/mcp-hub.test.ts`

**Step 1: Write the failing UI/service tests**

Add tests that expect:

- a new `Capability Mappings` tab is rendered in MCP Hub
- users can list mappings, preview a new mapping, and save it
- effective-policy views display resolved mapping provenance and unresolved capability warnings
- API client types include authored/resolved policy documents and mapping summaries

Example test shape:

```tsx
it("renders resolved mapping provenance in the persona policy summary", async () => {
  render(<PersonaPolicySummary personaId="researcher" />)
  expect(await screen.findByText("tool.invoke.research")).toBeTruthy()
  expect(screen.getByText(/Mapped by team research mapping/i)).toBeTruthy()
})
```

**Step 2: Run the focused UI tests to confirm they fail**

Run:

```bash
bunx vitest run \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/CapabilityMappingsTab.test.tsx \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/McpHubPage.test.tsx \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/PersonaPolicySummary.test.tsx \
  apps/packages/ui/src/services/tldw/__tests__/mcp-hub.test.ts
```

Expected: FAIL because the tab, client functions, and provenance UI do not exist yet.

**Step 3: Implement the UI and client updates**

Implement:

- client types and API calls for capability mapping CRUD/preview
- a new `CapabilityMappingsTab`
- new tab registration in `McpHubPage`
- resolved-policy visibility updates in `PersonaPolicySummary`

Keep the UI pragmatic:

- show mapping scope
- show capability name
- show previewed concrete effects
- show unresolved capability warnings

Do not redesign the whole MCP Hub page in this branch.

**Step 4: Re-run the focused UI tests**

Run:

```bash
bunx vitest run \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/CapabilityMappingsTab.test.tsx \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/McpHubPage.test.tsx \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/PersonaPolicySummary.test.tsx \
  apps/packages/ui/src/services/tldw/__tests__/mcp-hub.test.ts
```

Expected: PASS.

**Step 5: Run final focused verification and commit**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_capability_adapter_service.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_capability_adapter_api.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_capability_resolution.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_resolver.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_api.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_import.py -q

bunx vitest run \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/CapabilityMappingsTab.test.tsx \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/McpHubPage.test.tsx \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/PersonaPolicySummary.test.tsx \
  apps/packages/ui/src/services/tldw/__tests__/mcp-hub.test.ts

git diff --check

source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/services/mcp_hub_capability_adapter_service.py \
  tldw_Server_API/app/services/mcp_hub_capability_resolution_service.py \
  tldw_Server_API/app/services/mcp_hub_policy_resolver.py \
  tldw_Server_API/app/services/mcp_hub_governance_pack_service.py \
  tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py \
  -f json -o /tmp/bandit_capability_adapter_registry.json
```

Expected:

- pytest slices PASS
- vitest slice PASS
- `git diff --check` clean
- Bandit reports no new findings in touched backend files

Commit:

```bash
git add \
  apps/packages/ui/src/components/Option/MCPHub/CapabilityMappingsTab.tsx \
  apps/packages/ui/src/components/Option/MCPHub/McpHubPage.tsx \
  apps/packages/ui/src/components/Option/MCPHub/index.tsx \
  apps/packages/ui/src/components/Option/MCPHub/PersonaPolicySummary.tsx \
  apps/packages/ui/src/services/tldw/mcp-hub.ts \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/CapabilityMappingsTab.test.tsx \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/McpHubPage.test.tsx \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/PersonaPolicySummary.test.tsx \
  apps/packages/ui/src/services/tldw/__tests__/mcp-hub.test.ts
git commit -m "feat: add MCP Hub capability mapping UI"
```
