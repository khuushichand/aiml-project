# MCP Hub Shared Workspace Registry Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an admin-managed shared workspace registry that enables trusted `team`, `org`, and `global` workspace sets without changing existing user-local workspace handling.

**Architecture:** Introduce a new shared registry resource for trusted shared workspace roots, validate shared-scope workspace-set members against it, and teach runtime/effective previews to distinguish `user_local` versus `shared_registry` trust sources. Keep ingress unchanged: callers still send only `workspace_id` and `cwd`.

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

### Task 1: Add failing tests for the shared workspace registry and shared-scope workspace sets

**Files:**
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_workspace_set_objects.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py`
- Modify or Create: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_shared_workspace_registry.py`

**Step 1: Write failing registry CRUD tests**

Cover:

- create/list/update/delete shared registry entries
- reject `user` scope in the shared registry
- reject duplicate `(owner_scope_type, owner_scope_id, workspace_id)`
- reject ambiguous or invalid roots

**Step 2: Write failing shared workspace-set validation tests**

Cover:

- shared-scope workspace sets validate members only through the shared registry
- same-scope and parent-scope registry matches are allowed
- child-scope matches are rejected
- ambiguous matches fail closed

**Step 3: Write failing runtime/effective summary tests**

Cover:

- effective policy exposes `selected_workspace_trust_source`
- shared-scope assignment resolves through `shared_registry`
- workspace membership deny remains hard deny with no approval payload

**Step 4: Run focused tests and confirm failure**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_workspace_set_objects.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_shared_workspace_registry.py -k "workspace or registry" -v
```

Expected: FAIL.

### Task 2: Add storage and schema support for shared workspace registry entries

**Files:**
- Modify: `tldw_Server_API/app/core/AuthNZ/migrations.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py`
- Modify: `tldw_Server_API/tests/AuthNZ_SQLite/test_mcp_hub_migrations.py`
- Modify: `tldw_Server_API/tests/AuthNZ_Postgres/test_mcp_hub_pg_ensure.py`
- Modify: `tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_repo.py`

**Step 1: Add migrations**

Add a new shared registry table with:

- `workspace_id`
- `display_name`
- `absolute_root`
- `owner_scope_type`
- `owner_scope_id`
- `is_active`
- audit timestamps
- uniqueness on `(owner_scope_type, owner_scope_id, workspace_id)`

**Step 2: Add repo CRUD**

Implement:

- create/list/get/update/delete shared registry entries
- lookup helpers by `workspace_id` and scope compatibility
- referenced-entry checks for delete/update safety

**Step 3: Extend schemas**

Add request/response models for:

- shared registry entries
- effective policy trust-source field

**Step 4: Run focused storage tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/AuthNZ_SQLite/test_mcp_hub_migrations.py \
  tldw_Server_API/tests/AuthNZ_Postgres/test_mcp_hub_pg_ensure.py \
  tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_repo.py -k "workspace or registry or mcp_hub" -v
```

Expected: PASS.

### Task 3: Add service and API support with strict admin/system-configure gating

**Files:**
- Modify: `tldw_Server_API/app/services/mcp_hub_service.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_workspace_root_resolver.py`

**Step 1: Add shared registry validation helpers**

Implement:

- save-time root canonicalization for `absolute_root`
- shared-scope-only validation (`team`, `org`, `global`)
- same-scope / parent-scope lookup helpers
- ambiguity detection

**Step 2: Add stricter mutation authorization**

Require admin or `system.configure`-class authority for:

- create shared registry entry
- update shared registry entry
- delete shared registry entry

**Step 3: Add shared registry endpoints**

Add list/create/update/delete routes for shared workspace registry entries.

**Step 4: Block destructive changes while referenced**

Ensure:

- delete fails while referenced by any shared workspace set
- scope-changing updates fail while referenced

**Step 5: Run focused API tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_shared_workspace_registry.py -v
```

Expected: PASS.

### Task 4: Extend workspace-set validation and runtime trust-source selection

**Files:**
- Modify: `tldw_Server_API/app/services/mcp_hub_service.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_policy_resolver.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_workspace_root_resolver.py`
- Modify: `tldw_Server_API/app/core/MCP_unified/protocol.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_approval_service.py`

**Step 1: Extend workspace-set member validation**

Implement:

- user-scoped sets keep existing user-local validation
- shared-scope sets validate members through the shared registry
- require same-scope or parent-scope compatibility

**Step 2: Add trust-source resolution**

Return and use:

- `selected_workspace_trust_source = user_local | shared_registry`

**Step 3: Extend runtime resolution**

When a shared-scope workspace set is active:

- resolve active `workspace_id` through the shared registry
- reject child-scope or ambiguous matches
- hard deny on missing or disallowed shared workspace

**Step 4: Preserve deny-only behavior**

Ensure shared workspace membership failures:

- return deny-only reasons
- never emit approval payloads

**Step 5: Run focused runtime tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_workspace_set_objects.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_shared_workspace_registry.py -v
```

Expected: PASS.

### Task 5: Add MCP Hub UI for shared registry entries and shared trust-source summaries

**Files:**
- Modify: `apps/packages/ui/src/components/Option/MCPHub/McpHubPage.tsx`
- Create or Modify: `apps/packages/ui/src/components/Option/MCPHub/SharedWorkspacesTab.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/WorkspaceSetsTab.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/PolicyAssignmentsTab.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/PersonaPolicySummary.tsx`
- Modify: `apps/packages/ui/src/services/tldw/mcp-hub.ts`
- Modify or Create: `apps/packages/ui/src/components/Option/MCPHub/__tests__/*`

**Step 1: Add typed client support**

Add types and API calls for:

- shared registry entries
- effective trust-source fields

**Step 2: Add `Shared Workspaces` tab**

Implement admin-focused CRUD for shared registry entries.

**Step 3: Extend shared workspace-set editing**

When editing shared-scope workspace sets:

- use shared-registry-backed selection
- do not fall back to freeform user-local text

**Step 4: Extend summaries**

Show:

- workspace trust source
- shared registry identity where available

**Step 5: Run focused UI tests**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/components/Option/MCPHub/__tests__
```

Expected: PASS.

### Task 6: Add compatibility and regression coverage

**Files:**
- Modify: backend and UI test files from Tasks 1 through 5

**Step 1: Add user-local regression coverage**

Verify:

- existing user-scoped workspace sets still behave unchanged
- no shared registry dependency is introduced for user-local flows

**Step 2: Add scope-resolution regression coverage**

Verify:

- same-scope shared registry match wins over parent-scope
- ambiguous same-tier matches fail closed
- child-scope shared entries are ignored

**Step 3: Add destructive-change coverage**

Verify:

- referenced shared registry entries cannot be deleted
- referenced entries cannot be scope-moved while still referenced

**Step 4: Run broader focused suite**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_workspace_set_objects.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_shared_workspace_registry.py -v

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
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_workspace_set_objects.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_shared_workspace_registry.py \
  tldw_Server_API/tests/AuthNZ_SQLite/test_mcp_hub_migrations.py \
  tldw_Server_API/tests/AuthNZ_Postgres/test_mcp_hub_pg_ensure.py \
  tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_repo.py -v

cd apps/packages/ui && bunx vitest run src/components/Option/MCPHub/__tests__

source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py \
  tldw_Server_API/app/services/mcp_hub_service.py \
  tldw_Server_API/app/services/mcp_hub_workspace_root_resolver.py \
  tldw_Server_API/app/services/mcp_hub_policy_resolver.py \
  tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py \
  tldw_Server_API/app/core/MCP_unified/protocol.py \
  -f json -o /tmp/bandit_mcp_hub_shared_workspace_registry.json
```

Expected:

- focused backend suites PASS
- MCP Hub UI suites PASS
- Bandit reports no new findings in touched code

---

## Definition Of Done

- MCP Hub has an admin-managed shared workspace registry for `team`, `org`, and `global` scopes
- shared-scope workspace sets validate members only through that registry
- runtime resolves shared workspaces through deterministic same-scope / parent-scope lookup
- user-local workspace handling remains unchanged
- effective preview identifies `user_local` vs `shared_registry`
- shared workspace membership failures remain hard deny with no approval bypass
