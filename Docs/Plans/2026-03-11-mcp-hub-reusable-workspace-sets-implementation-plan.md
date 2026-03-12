# MCP Hub Reusable Workspace Sets Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add reusable user-scoped workspace-set objects for MCP Hub assignments while keeping one active trusted workspace per request/session and deny-only workspace membership enforcement.

**Architecture:** Introduce a first-class `WorkspaceSetObject` resource plus explicit assignment workspace-source fields (`workspace_source_mode`, `workspace_set_object_id`). Preserve existing inline assignment workspace rows for backward compatibility, but let runtime select exactly one membership source and validate named workspace sets against the trusted user-scoped workspace resolver before storing them.

**Tech Stack:** FastAPI, MCP Hub AuthNZ repo/services/endpoints, MCP workspace/path services, React/Ant Design MCP Hub UI, pytest, Vitest, Bandit

---

## Status

- Task 1: Complete
- Task 2: Complete
- Task 3: Complete
- Task 4: Complete
- Task 5: Complete
- Task 6: Complete
- Task 7: Complete

### Task 1: Add failing tests for named workspace-set objects and assignment workspace source mode

**Files:**
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_resolver.py`
- Modify or Create: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_workspace_set_objects.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py`

**Step 1: Add failing CRUD tests for workspace-set objects**

Cover:

- create/list/update/delete
- user-scope-only restriction
- member uniqueness
- unresolved or ambiguous `workspace_id` rejection

**Step 2: Add failing assignment source-mode tests**

Cover:

- assignment save with `workspace_source_mode = inline`
- assignment save with `workspace_source_mode = named`
- reject named source when `workspace_set_object_id` is missing
- reject named source on non-user-scoped assignments
- preserve inline rows when switching to named source

**Step 3: Add failing runtime/effective preview tests**

Cover:

- effective preview exposes:
  - `selected_workspace_source_mode`
  - `selected_workspace_set_object_id`
  - `selected_workspace_set_object_name`
- runtime hard-denies `workspace_not_allowed_for_assignment` when named set misses
- runtime still ignores preserved inline rows while named source is active

**Step 4: Run focused tests and confirm failure**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_resolver.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_workspace_set_objects.py -k "workspace" -v
```

Expected: FAIL.

### Task 2: Add storage and schema support for workspace-set objects and assignment workspace source fields

**Files:**
- Modify: `tldw_Server_API/app/core/AuthNZ/migrations.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py`
- Modify: `tldw_Server_API/tests/AuthNZ_SQLite/test_mcp_hub_migrations.py`
- Modify: `tldw_Server_API/tests/AuthNZ_Postgres/test_mcp_hub_pg_ensure.py`
- Modify: `tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_repo.py`

**Step 1: Add migration coverage**

Add:

- `mcp_workspace_set_objects`
- `mcp_workspace_set_object_members`
- `workspace_source_mode` on `mcp_policy_assignments`
- nullable `workspace_set_object_id` on `mcp_policy_assignments`
- uniqueness/index constraints

**Step 2: Add repo CRUD**

Implement:

- workspace-set object CRUD
- workspace-set member CRUD
- assignment read/write for `workspace_source_mode` and `workspace_set_object_id`
- referenced-object delete blocking

**Step 3: Add schema types**

Add request/response models for:

- workspace-set objects
- workspace-set members
- assignment workspace source fields
- effective policy workspace-source summary fields

**Step 4: Run focused repo/migration tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/AuthNZ_SQLite/test_mcp_hub_migrations.py \
  tldw_Server_API/tests/AuthNZ_Postgres/test_mcp_hub_pg_ensure.py \
  tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_repo.py -k "workspace" -v
```

Expected: PASS.

### Task 3: Add MCP Hub service and API support with write-time trusted workspace validation

**Files:**
- Modify: `tldw_Server_API/app/services/mcp_hub_service.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_workspace_root_resolver.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py`

**Step 1: Add server-side validation helpers**

Implement helpers that:

- enforce `WorkspaceSetObject` user scope only
- validate member `workspace_id`s against the trusted resolver path for the owning user
- validate assignment `workspace_source_mode`
- validate named-source references and same-user ownership

**Step 2: Add workspace-set object endpoints**

Add list/create/update/delete routes for `WorkspaceSetObject` and member CRUD routes.

**Step 3: Extend assignment create/update routes**

Persist and validate:

- `workspace_source_mode`
- `workspace_set_object_id`

Reject invalid source combinations clearly.

**Step 4: Block deletes while referenced**

Ensure delete routes return a validation error when a workspace-set object is still referenced by any assignment.

**Step 5: Run focused API tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_workspace_set_objects.py -v
```

Expected: PASS.

### Task 4: Extend effective policy resolution and runtime membership selection

**Files:**
- Modify: `tldw_Server_API/app/services/mcp_hub_policy_resolver.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_path_scope_service.py`
- Modify: `tldw_Server_API/app/core/MCP_unified/protocol.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_approval_service.py`

**Step 1: Resolve selected workspace membership source**

Implement:

- `workspace_source_mode = inline` -> current assignment workspace rows
- `workspace_source_mode = named` -> referenced workspace-set object members
- no configured source -> current backward-compatible behavior

**Step 2: Extend effective policy summary**

Return:

- `selected_workspace_source_mode`
- `selected_workspace_set_object_id`
- `selected_workspace_set_object_name`
- `selected_assignment_workspace_ids`

**Step 3: Keep workspace membership deny-only**

If active trusted `workspace_id` is not in the selected source:

- hard deny
- `workspace_not_allowed_for_assignment`
- no approval payload

**Step 4: Run focused runtime tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_resolver.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_workspace_set_objects.py -v
```

Expected: PASS.

### Task 5: Add MCP Hub UI for workspace sets and assignment source switching

**Files:**
- Modify: `apps/packages/ui/src/components/Option/MCPHub/McpHubPage.tsx`
- Create or Modify: `apps/packages/ui/src/components/Option/MCPHub/WorkspaceSetsTab.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/PolicyAssignmentsTab.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/PersonaPolicySummary.tsx`
- Modify: `apps/packages/ui/src/services/tldw/mcp-hub.ts`
- Modify or Create: `apps/packages/ui/src/components/Option/MCPHub/__tests__/*`

**Step 1: Add typed client support**

Add types and API calls for:

- workspace-set objects
- workspace-set members
- assignment `workspace_source_mode`
- assignment `workspace_set_object_id`
- effective preview workspace-source fields

**Step 2: Add `Workspace Sets` tab**

Implement CRUD for user-scoped workspace-set objects and member editing.

**Step 3: Extend assignments UI**

Add:

- `Workspace Access Source` selector
- named workspace-set picker
- preserved inline workspace list display while named mode is active

Make `syncAssignmentWorkspaces(...)` run only in inline mode.

**Step 4: Extend summaries and preview**

Show:

- workspace source mode
- selected workspace-set object name
- effective workspace ids

**Step 5: Run focused UI tests**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/components/Option/MCPHub/__tests__
```

Expected: PASS.

### Task 6: Add compatibility and regression coverage

**Files:**
- Modify: backend and UI test files from Tasks 1 through 5

**Step 1: Add backward-compat tests**

Cover:

- existing inline assignment workspace rows still work unchanged
- assignments with no source configured keep current behavior
- switching between inline and named source preserves inline rows

**Step 2: Add deletion/reference coverage**

Verify:

- referenced workspace-set objects cannot be deleted
- switching back to inline reactivates preserved inline rows

**Step 3: Add deny-only coverage**

Verify `workspace_not_allowed_for_assignment` never emits approval payloads under named source mode.

**Step 4: Run broader focused suite**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_resolver.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_workspace_set_objects.py -v

cd apps/packages/ui && bunx vitest run src/components/Option/MCPHub/__tests__
```

Expected: PASS.

### Task 7: Final verification, Bandit, and docs touch-up

**Files:**
- Modify: touched docs if implementation details drift

**Step 1: Run final focused verification**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_resolver.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_workspace_set_objects.py \
  tldw_Server_API/tests/AuthNZ_SQLite/test_mcp_hub_migrations.py \
  tldw_Server_API/tests/AuthNZ_Postgres/test_mcp_hub_pg_ensure.py \
  tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_repo.py -v

cd apps/packages/ui && bunx vitest run src/components/Option/MCPHub/__tests__

source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py \
  tldw_Server_API/app/services/mcp_hub_service.py \
  tldw_Server_API/app/services/mcp_hub_policy_resolver.py \
  tldw_Server_API/app/services/mcp_hub_workspace_root_resolver.py \
  tldw_Server_API/app/core/MCP_unified/protocol.py \
  tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py \
  -f json -o /tmp/bandit_mcp_hub_reusable_workspace_sets.json
```

Expected:

- focused backend suites PASS
- UI MCP Hub suites PASS
- Bandit reports no new findings in touched code

---

## Definition Of Done

- MCP Hub has first-class reusable user-scoped workspace-set objects
- assignments use explicit `workspace_source_mode` and `workspace_set_object_id`
- named and inline workspace membership do not merge in v1
- preserved inline rows survive source switches without affecting named-mode runtime behavior
- runtime denies requests whose active trusted workspace is not in the selected source
- effective preview clearly shows workspace source identity and effective ids
