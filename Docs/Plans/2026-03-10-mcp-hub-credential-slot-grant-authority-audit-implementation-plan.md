# MCP Hub Credential Slot Grant Authority And Audit Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enforce privilege-aware grant authority for MCP Hub credential-slot grants and slot privilege-class escalation, cover server-level default-slot binding routes, and enrich successful audit metadata without redesigning runtime external access.

**Architecture:** Tighten slot `privilege_class` to the enum `read | write | admin`, add endpoint-layer grant-authority helpers in MCP Hub management routes, resolve effective slots for both explicit-slot and compatible server-level binding routes, keep assignment `disable` authority-free, and extend successful audit metadata for grants and privilege elevation. Service and runtime access resolution remain otherwise unchanged.

**Tech Stack:** FastAPI, AuthNZ SQLite/Postgres persistence, MCP Hub services, React, Ant Design, pytest, Vitest, Bandit

---

## Status

- Task 1: Not started
- Task 2: Not started
- Task 3: Not started
- Task 4: Not started
- Task 5: Not started
- Task 6: Not started
- Task 7: Not started

### Task 1: Add failing tests for slot grant authority and privilege escalation

**Files:**
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_service.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_access_resolver.py`

**Step 1: Add API-level failing tests**

Add tests that expect:

- profile read-slot grant succeeds with `grant.credentials.read`
- profile write-slot grant fails with only `grant.credentials.read`
- profile admin-slot grant succeeds with `grant.credentials.admin`
- assignment disable succeeds without credential grant permissions
- server-level profile binding route requires authority for the compatible
  default slot
- slot create with `admin` privilege fails without `grant.credentials.admin`
- slot update from `read` to `write` fails without `grant.credentials.write`

**Step 2: Add audit expectation tests**

Add tests that expect successful grant mutations include metadata for:

- `slot_name`
- `privilege_class`
- `required_permission`

Mock the MCP Hub audit emitter if needed rather than reaching through the full
audit system.

**Step 3: Run the focused tests to confirm failure**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_service.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_access_resolver.py \
  -k "credential or slot or grant" -v
```

Expected: FAIL.

**Step 4: Commit**

```bash
git add \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_service.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_access_resolver.py
git commit -m "test: add MCP Hub credential grant authority coverage"
```

### Task 2: Tighten privilege-class normalization to a real enum

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_service.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_service.py`

**Step 1: Add canonical privilege-class normalization**

Normalize and validate `privilege_class` as:

- `read`
- `write`
- `admin`

Reject unknown values on slot create/update with `400`.

**Step 2: Ensure repo/service normalization stays consistent**

Update slot create/update flows so:

- stored values are canonical lowercase enum values
- legacy freeform privilege classes no longer enter through public write paths

**Step 3: Run targeted schema/service tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_service.py \
  -k "privilege or slot" -v
```

Expected: PASS.

**Step 4: Commit**

```bash
git add \
  tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py \
  tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py \
  tldw_Server_API/app/services/mcp_hub_service.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_service.py
git commit -m "feat: tighten MCP Hub slot privilege classes"
```

### Task 3: Add shared HTTP-layer credential grant-authority helpers

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py`

**Step 1: Add helper functions**

Implement endpoint-layer helpers for:

- privilege-class rank lookup
- required-permission mapping
- ladder satisfaction check
- resolving the effective slot for a binding route
- resolving whether a slot privilege update broadens access

**Step 2: Keep enforcement narrow and explicit**

Helpers should:

- mirror the existing `_require_grant_authority(...)` pattern
- operate only on public MCP Hub mutation routes
- support explicit slot routes and compatible server-level default-slot routes

**Step 3: Run the focused API tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py \
  -k "credential or slot or grant" -v
```

Expected: PASS once helpers are wired.

**Step 4: Commit**

```bash
git add \
  tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py
git commit -m "feat: add MCP Hub credential grant checks"
```

### Task 4: Enforce grant authority on binding grant routes

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py`

**Step 1: Apply checks to profile binding grant routes**

Before calling the service for:

- `/permission-profiles/{profile_id}/credential-bindings/{server_id}`
- `/permission-profiles/{profile_id}/credential-bindings/{server_id}/{slot_name}`

enforce the required credential grant authority when the binding mode is
`grant`.

**Step 2: Apply checks to assignment binding grant routes**

Before calling the service for:

- `/policy-assignments/{assignment_id}/credential-bindings/{server_id}`
- `/policy-assignments/{assignment_id}/credential-bindings/{server_id}/{slot_name}`

enforce the required credential grant authority only when:

- `binding_mode == "grant"`

Do not require it for:

- `binding_mode == "disable"`
- delete routes

**Step 3: Run the focused API tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py \
  -k "profile_credential or assignment_credential or default_slot" -v
```

Expected: PASS.

**Step 4: Commit**

```bash
git add \
  tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py
git commit -m "feat: enforce MCP Hub slot grant authority"
```

### Task 5: Enforce privilege escalation checks on slot create and update

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py`

**Step 1: Apply checks to slot create**

Creating a slot requires authority for its requested privilege class.

**Step 2: Apply checks to slot update**

Updating a slot requires authority only when the privilege class broadens, for
example:

- `read -> write`
- `write -> admin`
- `read -> admin`

Lowering or keeping the same class requires only normal mutation permission.

**Step 3: Run focused slot API tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py \
  -k "credential_slot" -v
```

Expected: PASS.

**Step 4: Commit**

```bash
git add \
  tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py
git commit -m "feat: enforce MCP Hub slot privilege escalation"
```

### Task 6: Enrich successful MCP Hub audit metadata

**Files:**
- Modify: `tldw_Server_API/app/services/mcp_hub_service.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_service.py`

**Step 1: Extend successful binding audit metadata**

For successful profile and assignment binding grants, include:

- `slot_name`
- `privilege_class`
- `required_permission`
- `binding_mode`
- target type and id

**Step 2: Extend successful slot privilege mutation audit metadata**

For slot create/update, include:

- `slot_name`
- resulting `privilege_class`
- prior `privilege_class` when updating
- `required_permission` when the mutation broadened access

Keep denied-attempt audit out of scope.

**Step 3: Run focused service tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_service.py \
  -k "audit or privilege" -v
```

Expected: PASS.

**Step 4: Commit**

```bash
git add \
  tldw_Server_API/app/services/mcp_hub_service.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_service.py
git commit -m "feat: audit MCP Hub credential privilege grants"
```

### Task 7: Surface 403 details cleanly in the MCP Hub UI and verify

**Files:**
- Modify: `apps/packages/ui/src/components/Option/MCPHub/PermissionProfilesTab.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/PolicyAssignmentsTab.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/ExternalServersTab.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/PermissionProfilesTab.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/PolicyAssignmentsTab.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/ExternalServersTab.test.tsx`

**Step 1: Preserve backend 403 error detail**

Ensure binding and slot privilege mutation flows surface the backend message
cleanly, especially:

- `Grant authority required: grant.credentials.write`
- `Grant authority required: grant.credentials.admin`

**Step 2: Add focused UI tests**

Add tests that mock `403` failures and verify the message is shown.

**Step 3: Run focused verification**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_management_api.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_service.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_external_access_resolver.py -v

bunx vitest run src/components/Option/MCPHub/__tests__

source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py \
  tldw_Server_API/app/services/mcp_hub_service.py \
  tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py \
  tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py \
  -f json -o /tmp/bandit_mcp_hub_credential_grant_authority.json
```

Expected:

- focused pytest suites PASS
- Vitest MCP Hub suite PASS
- Bandit reports no new findings in touched code

**Step 4: Commit**

```bash
git add \
  apps/packages/ui/src/components/Option/MCPHub/PermissionProfilesTab.tsx \
  apps/packages/ui/src/components/Option/MCPHub/PolicyAssignmentsTab.tsx \
  apps/packages/ui/src/components/Option/MCPHub/ExternalServersTab.tsx \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/PermissionProfilesTab.test.tsx \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/PolicyAssignmentsTab.test.tsx \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/ExternalServersTab.test.tsx
git commit -m "feat: surface MCP Hub credential grant authority errors"
```

---

## Definition Of Done

- Slot `privilege_class` is validated as `read | write | admin`
- Binding grant routes enforce privilege-aware grant authority
- Single-slot compatible server-level binding routes cannot bypass slot
  authority
- Assignment `disable` remains authority-free
- Slot privilege-class elevation is enforced on create/update
- Successful audit metadata records slot privilege and required permission
- MCP Hub UI surfaces backend `403` grant-authority errors clearly
- Focused pytest, Vitest, and Bandit verification pass
