# MCP Hub Workspace Membership Runtime Approval Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add tool-specific runtime approval for trusted-but-unassigned workspaces while keeping unresolvable workspaces as hard deny.

**Architecture:** Reorder workspace evaluation so trust-source resolution happens before assignment membership checks, classify trusted-vs-unresolvable workspace misses separately, extend approval scoping with assignment and trust-source identity, and forward a workspace governance payload through the persona runtime bridge.

**Tech Stack:** FastAPI, MCP Unified protocol layer, MCP Hub path scope/enforcement services, MCP Hub approval service, persona WebSocket endpoint, React, Vitest, pytest, Bandit

---

## Status

- Task 1: Not Started
- Task 2: Not Started
- Task 3: Not Started
- Task 4: Not Started
- Task 5: Not Started
- Task 6: Not Started

### Task 1: Add failing backend and UI tests for workspace-membership approval

**Files:**
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py`
- Modify or Create: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_workspace_membership_approval.py`
- Modify: `tldw_Server_API/tests/Persona/test_persona_ws.py`
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`

**Step 1: Write failing backend tests**

Add tests that expect:

- trusted resolvable workspace outside assignment membership yields approval-required
- unresolvable workspace yields hard deny and no approval payload
- approval scope changes when tool name changes
- approval scope changes when assignment id changes
- approval scope changes when workspace trust source changes

**Step 2: Write failing persona bridge tests**

Add tests that expect:

- workspace approval payload is forwarded in `tool_result`
- unresolvable workspace denial forwards a workspace/path governance payload

**Step 3: Write failing UI tests**

Add tests that expect:

- persona approval card renders denied trusted `workspace_id`
- hard deny shows trust-source failure text
- hard deny shows no approval buttons

**Step 4: Run focused tests to confirm failure**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_workspace_membership_approval.py \
  tldw_Server_API/tests/Persona/test_persona_ws.py -k "workspace and approval" -v

cd apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: FAIL.

### Task 2: Reorder workspace evaluation and classify trusted-vs-unresolvable misses

**Files:**
- Modify: `tldw_Server_API/app/services/mcp_hub_path_scope_service.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_path_enforcement_service.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py`
- Modify or Create: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_workspace_membership_approval.py`

**Step 1: Write minimal classification logic**

Change path/workspace evaluation so it:

- checks resolver failure before assignment membership
- returns `workspace_unresolvable_for_trust_source` when trust resolution fails
- returns `workspace_not_allowed_but_trusted` when the workspace resolves but is excluded from assignment membership

**Step 2: Extend scope payload**

Ensure the blocked scope payload includes:

- `workspace_id`
- `selected_workspace_trust_source`
- `selected_assignment_id`
- `workspace_source_mode`
- `allowed_workspace_ids`

**Step 3: Run focused backend tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_workspace_membership_approval.py -k "workspace" -v
```

Expected: PASS.

### Task 3: Extend approval hashing and protocol routing for workspace approvals

**Files:**
- Modify: `tldw_Server_API/app/services/mcp_hub_approval_service.py`
- Modify: `tldw_Server_API/app/core/MCP_unified/protocol.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py`
- Modify or Create: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_workspace_membership_approval.py`

**Step 1: Extend approval scope fingerprinting**

Add the workspace approval fields to the approval scope hash:

- `workspace_id`
- `selected_assignment_id`
- `workspace_source_mode`
- `selected_workspace_trust_source`

**Step 2: Change protocol behavior**

Update protocol handling so:

- `workspace_unresolvable_for_trust_source` remains a deny-only governance error
- `workspace_not_allowed_but_trusted` is eligible for runtime approval
- approval is still exact to the current tool and workspace context

**Step 3: Run focused approval tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_workspace_membership_approval.py -k "approval or workspace" -v
```

Expected: PASS.

### Task 4: Forward workspace governance payloads through the persona WebSocket bridge

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/persona.py`
- Modify: `tldw_Server_API/tests/Persona/test_persona_ws.py`

**Step 1: Add workspace/path governance forwarding**

Extend the persona bridge so `tool_result` can forward:

- approval payload with workspace/path `scope_context`
- deny payload with workspace/path governance details

Keep external-access forwarding unchanged.

**Step 2: Run focused persona bridge tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Persona/test_persona_ws.py -k "workspace and approval" -v
```

Expected: PASS.

### Task 5: Update the persona runtime UI for workspace approval and hard deny

**Files:**
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`

**Step 1: Generalize approval/deny scope parsing**

Add a workspace/path governance context shape that can represent:

- trusted denied `workspace_id`
- trust source
- assignment identity if present
- deny-only reason

**Step 2: Render workspace approval cards**

For approval-required workspace cases, show:

- tool name
- trusted denied `workspace_id`
- trust-source context
- normal duration selector and approve/deny actions

**Step 3: Render workspace hard-deny messaging**

For unresolvable workspace cases, show:

- explicit trust-source failure messaging
- no approval controls

**Step 4: Run focused UI tests**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: PASS.

### Task 6: Final verification, Bandit, docs touch-up, and commit

**Files:**
- Modify: touched docs if implementation details drift

**Step 1: Run final focused backend verification**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_workspace_membership_approval.py \
  tldw_Server_API/tests/Persona/test_persona_ws.py -v
```

Expected: PASS.

**Step 2: Run final UI verification**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: PASS.

**Step 3: Run Bandit on touched backend scope**

Run:

```bash
source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/services/mcp_hub_path_scope_service.py \
  tldw_Server_API/app/services/mcp_hub_path_enforcement_service.py \
  tldw_Server_API/app/services/mcp_hub_approval_service.py \
  tldw_Server_API/app/core/MCP_unified/protocol.py \
  tldw_Server_API/app/api/v1/endpoints/persona.py \
  -f json -o /tmp/bandit_mcp_hub_workspace_membership_runtime_approval.json
```

Expected:

- Bandit reports no new findings in touched code

**Step 4: Commit**

```bash
git add <touched files>
git commit -m "feat: add workspace membership runtime approval"
```

---

## Definition Of Done

- trusted-but-unassigned workspaces can trigger runtime approval
- unresolvable workspaces remain hard deny
- approval scope is exact to tool, workspace id, assignment, and trust source
- persona runtime UI distinguishes workspace approval from trust-source hard deny
- stored assignment workspace membership remains unchanged
