# MCP Hub Multi-Root Path Scope Objects Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add reusable named path-scope objects and assignment-level trusted workspace sets while keeping one active trusted workspace per request/session for runtime path enforcement.

**Architecture:** Introduce a first-class `PathScopeObject` MCP Hub resource with explicit `path_scope_object_id` references on profiles and assignments, then add assignment-only workspace membership records checked before existing path extraction/enforcement. Runtime keeps the current path model and treats workspace membership misses as hard denials, while previews and provenance surface object vs inline replacement clearly.

**Tech Stack:** FastAPI, MCP Hub AuthNZ repo/services/endpoints, MCP protocol/path services, React/Ant Design MCP Hub UI, pytest, Vitest, Bandit

---

## Status

- Task 1: Complete
- Task 2: Complete
- Task 3: Complete
- Task 4: Complete
- Task 5: Complete
- Task 6: Complete
- Task 7: Complete

### Task 1: Add failing backend tests for path-scope objects and assignment workspace sets

**Files:**
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_resolver.py`
- Modify or Create: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_path_scope_objects.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py`

**Step 1: Add failing CRUD tests for path-scope objects**

Cover:

- create/list/update/delete
- reference same-scope and parent-scope objects
- reject child-scope references

**Step 2: Add failing workspace-set tests**

Cover:

- add/remove/list assignment workspace ids
- uniqueness on `(assignment_id, workspace_id)`
- no-workspace-set backward compatibility

**Step 3: Add failing runtime/provenance tests**

Cover:

- path object + inline + override layer order
- `workspace_not_allowed_for_assignment` hard deny
- approval scope differs when `workspace_id` differs

**Step 4: Run focused tests and confirm failure**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_resolver.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py -k "path scope or workspace" -v
```

Expected: FAIL.

### Task 2: Add storage and schema support for path-scope objects and workspace membership

**Files:**
- Modify: `tldw_Server_API/app/core/AuthNZ/migrations.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py`
- Modify: repo-level AuthNZ migration/repo tests that cover MCP Hub persistence

**Step 1: Add migration coverage**

Add:

- `mcp_path_scope_objects`
- nullable `path_scope_object_id` on profiles and assignments
- `mcp_policy_assignment_workspaces`
- uniqueness/index constraints

**Step 2: Add repo CRUD**

Implement:

- path-scope object CRUD
- assignment workspace membership CRUD
- profile/assignment `path_scope_object_id` persistence

**Step 3: Add schema types**

Add request/response models for:

- path-scope objects
- assignment workspace membership
- path-scope object summaries on profile/assignment responses

**Step 4: Run focused repo/migration tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/AuthNZ_SQLite/test_mcp_hub_migrations.py \
  tldw_Server_API/tests/AuthNZ_Postgres/test_mcp_hub_pg_ensure.py \
  tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_repo.py -k "path scope or workspace" -v
```

Expected: PASS.

### Task 3: Add MCP Hub service and API support with scope-safe reference validation

**Files:**
- Modify: `tldw_Server_API/app/services/mcp_hub_service.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py`

**Step 1: Add server-side validation helpers**

Implement helpers that:

- normalize/validate `path_scope_document`
- validate `path_scope_object_id`
- enforce same-scope or parent-scope reference rules

**Step 2: Add path-scope object endpoints**

Add list/create/update/delete routes for `PathScopeObject`.

**Step 3: Add assignment workspace membership endpoints**

Add nested routes under assignments for workspace membership CRUD.

**Step 4: Extend profile and assignment create/update routes**

Persist and validate explicit `path_scope_object_id` references.

**Step 5: Run focused API tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_path_scope_objects.py -v
```

Expected: PASS.

### Task 4: Extend effective policy resolution and runtime hard-deny behavior

**Files:**
- Modify: `tldw_Server_API/app/services/mcp_hub_policy_resolver.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_path_scope_service.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_approval_service.py`
- Modify: `tldw_Server_API/app/core/MCP_unified/protocol.py`

**Step 1: Load path-scope object layers explicitly**

Apply this order:

1. profile object
2. profile inline path fields
3. assignment object
4. assignment inline path fields
5. assignment override path fields

**Step 2: Add provenance and summary fields**

Return path-scope object source explicitly in effective policy/provenance output.

**Step 3: Enforce assignment workspace membership before path extraction**

If the active trusted `workspace_id` is not in the assignment workspace set, return:

- hard deny
- reason `workspace_not_allowed_for_assignment`
- no approval payload

**Step 4: Include active `workspace_id` in path approval scope**

Ensure path approval reuse cannot cross allowed workspaces.

**Step 5: Run focused runtime tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_resolver.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py -v
```

Expected: PASS.

### Task 5: Add MCP Hub UI for path-scope objects and assignment workspace access

**Files:**
- Modify: `apps/packages/ui/src/components/Option/MCPHub/McpHubPage.tsx`
- Create or Modify: `apps/packages/ui/src/components/Option/MCPHub/PathScopesTab.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/PolicyAssignmentsTab.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/PolicyDocumentEditor.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/PersonaPolicySummary.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/policyHelpers.ts`
- Modify: `apps/packages/ui/src/services/tldw/mcp-hub.ts`
- Modify or Create: `apps/packages/ui/src/components/Option/MCPHub/__tests__/*`

**Step 1: Add typed client support**

Add types and API calls for:

- path-scope objects
- assignment workspace membership
- profile/assignment `path_scope_object_id`

**Step 2: Add `Path Scopes` tab**

Implement CRUD using the existing guided path controls.

**Step 3: Extend assignment/profile editing**

Add:

- `Path Scope Source` selector
- named object picker
- workspace membership editor

Preserve inline path state when switching source modes.

**Step 4: Extend summaries and preview**

Show:

- path object source
- replacement semantics
- workspace membership

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

- existing inline path rules with no named object
- assignments with no workspace set keep current behavior
- switching between inline and named path sources preserves inline state

**Step 2: Add deny-only coverage**

Verify `workspace_not_allowed_for_assignment` never emits approval UI payloads.

**Step 3: Run broader focused suite**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_resolver.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_path_scope_objects.py -v

cd apps/packages/ui && bunx vitest run src/components/Option/MCPHub/__tests__
```

Expected: PASS.

### Task 7: Final verification, Bandit, and docs touch-up

**Files:**
- Modify: any touched docs if implementation details drift

**Step 1: Run final focused verification**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_resolver.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_path_scope_objects.py \
  tldw_Server_API/tests/AuthNZ_SQLite/test_mcp_hub_migrations.py \
  tldw_Server_API/tests/AuthNZ_Postgres/test_mcp_hub_pg_ensure.py \
  tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_repo.py -v

cd apps/packages/ui && bunx vitest run src/components/Option/MCPHub/__tests__

source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py \
  tldw_Server_API/app/services/mcp_hub_service.py \
  tldw_Server_API/app/services/mcp_hub_policy_resolver.py \
  tldw_Server_API/app/services/mcp_hub_path_scope_service.py \
  tldw_Server_API/app/services/mcp_hub_approval_service.py \
  tldw_Server_API/app/core/MCP_unified/protocol.py \
  tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py \
  -f json -o /tmp/bandit_mcp_hub_multi_root_path_scope_objects.json
```

Expected:

- focused backend suites PASS
- UI MCP Hub suites PASS
- Bandit reports no new findings in touched code

---

## Definition Of Done

- MCP Hub has first-class reusable path-scope objects
- Profiles and assignments can reference same-scope or parent-scope path objects explicitly
- Assignments can restrict trusted workspace membership with unique workspace-set records
- Runtime denies requests whose active trusted workspace is not allowed for the assignment
- Existing inline path rules and assignments without workspace sets continue to work unchanged
- Effective preview and provenance show object-vs-inline path layering clearly
