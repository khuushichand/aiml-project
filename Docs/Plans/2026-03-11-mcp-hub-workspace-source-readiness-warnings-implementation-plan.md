# MCP Hub Workspace Source Readiness Warnings Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add advisory multi-root readiness summaries for reusable workspace sources and surface them in `Workspace Sets`, `Shared Workspaces`, and the assignment editor's named workspace-set picker.

**Architecture:** Add a shared `readiness_summary` DTO to workspace-set and shared-workspace list rows, compute those summaries server-side in batched list-oriented service helpers, and render them in the existing MCP Hub tabs and assignment picker without changing enforcement.

**Tech Stack:** FastAPI, MCP Hub service layer, MCP Hub schemas/endpoints, React/Ant Design MCP Hub UI, pytest, Vitest, Bandit

---

## Status

- Task 1: Complete
- Task 2: Complete
- Task 3: Complete
- Task 4: Complete
- Task 5: Complete

### Task 1: Add failing backend and UI tests for readiness summaries

**Files:**
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py`
- Modify or Create: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_workspace_source_readiness.py`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/WorkspaceSetsTab.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/SharedWorkspacesTab.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/PolicyAssignmentsTab.test.tsx`

**Step 1: Add failing backend readiness-summary tests**

Cover:

- workspace-set list row includes `readiness_summary`
- overlap produces `multi_root_overlap_warning`
- unresolved workspace id produces `workspace_unresolvable_warning`
- shared-workspace list row includes overlap readiness against visible entries

**Step 2: Add failing UI tests**

Cover:

- workspace-set row renders readiness warning
- shared-workspace row renders readiness warning
- assignment named workspace-set picker shows readiness label

**Step 3: Run focused tests to confirm failure**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_workspace_source_readiness.py -v

cd apps/packages/ui && bunx vitest run \
  src/components/Option/MCPHub/__tests__/WorkspaceSetsTab.test.tsx \
  src/components/Option/MCPHub/__tests__/SharedWorkspacesTab.test.tsx \
  src/components/Option/MCPHub/__tests__/PolicyAssignmentsTab.test.tsx
```

Expected: FAIL.

### Task 2: Add shared readiness-summary DTOs and service helpers

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_service.py`
- Modify or Create: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_workspace_source_readiness.py`

**Step 1: Add shared summary schema**

Add a reusable readiness-summary model and include it on:

- `WorkspaceSetObjectResponse`
- `SharedWorkspaceResponse`

**Step 2: Add service helpers**

Implement non-throwing summary helpers for:

- workspace sets
- shared workspaces

Rules:

- compute advisory readiness only
- use same trust-source semantics as current runtime
- shared-workspace overlap compares only same-scope and parent-scope visible entries

**Step 3: Run focused backend tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_workspace_source_readiness.py -v
```

Expected: PASS.

### Task 3: Return readiness summaries inline on list endpoints

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_service.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py`

**Step 1: Workspace-set list response**

Attach `readiness_summary` inline to `list_workspace_set_objects`.

**Step 2: Shared-workspace list response**

Attach `readiness_summary` inline to `list_shared_workspaces`.

**Step 3: Run focused API tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py -k "workspace set or shared workspace" -v
```

Expected: PASS.

### Task 4: Render advisory warnings in tabs and assignment picker

**Files:**
- Modify: `apps/packages/ui/src/services/tldw/mcp-hub.ts`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/WorkspaceSetsTab.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/SharedWorkspacesTab.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/PolicyAssignmentsTab.tsx`
- Modify relevant MCP Hub UI tests

**Step 1: Mirror readiness-summary types in the client**

Update shared-workspace and workspace-set types to include readiness summary.

**Step 2: Workspace Sets and Shared Workspaces**

Render advisory warning labels/details in list rows.

**Step 3: Assignment picker**

Render readiness labels for named workspace sets and show a local warning for
the selected non-ready set.

**Step 4: Run focused UI tests**

Run:

```bash
cd apps/packages/ui && bunx vitest run \
  src/components/Option/MCPHub/__tests__/WorkspaceSetsTab.test.tsx \
  src/components/Option/MCPHub/__tests__/SharedWorkspacesTab.test.tsx \
  src/components/Option/MCPHub/__tests__/PolicyAssignmentsTab.test.tsx
```

Expected: PASS.

### Task 5: Final verification, docs update, and commit

**Files:**
- Modify: `Docs/Plans/2026-03-11-mcp-hub-workspace-source-readiness-warnings-design.md`
- Modify: `Docs/Plans/2026-03-11-mcp-hub-workspace-source-readiness-warnings-implementation-plan.md`

**Step 1: Run focused backend verification**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_workspace_source_readiness.py -v
```

**Step 2: Run focused UI verification**

Run:

```bash
cd apps/packages/ui && bunx vitest run \
  src/components/Option/MCPHub/__tests__/WorkspaceSetsTab.test.tsx \
  src/components/Option/MCPHub/__tests__/SharedWorkspacesTab.test.tsx \
  src/components/Option/MCPHub/__tests__/PolicyAssignmentsTab.test.tsx
```

**Step 3: Run Bandit on touched backend scope**

Run:

```bash
source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/services/mcp_hub_service.py \
  tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py
```

**Step 4: Mark docs implemented and commit**

Commit message:

```bash
git commit -m "feat: add workspace source readiness warnings"
```
