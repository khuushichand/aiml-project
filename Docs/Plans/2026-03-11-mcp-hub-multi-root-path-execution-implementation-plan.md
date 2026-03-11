# MCP Hub Multi-Root Path Execution Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add narrow multi-root path execution for `path_boundable` tools by mapping exact normalized paths onto an already-trusted, already-allowed workspace bundle.

**Architecture:** Keep the current single-root path resolver intact, add a bundle-mapping layer above it, anchor relative paths to the active workspace only, deny ambiguous or unallowed workspace matches, and extend approval scoping to the exact normalized path set across the exact workspace bundle.

**Tech Stack:** FastAPI, MCP Hub path/workspace services, MCP Unified protocol, React persona runtime UI, pytest, Vitest, Bandit

---

## Status

- Task 1: Complete
- Task 2: Complete
- Task 3: Complete
- Task 4: Complete
- Task 5: Complete
- Task 6: Complete

### Task 1: Add failing tests for multi-root mapping, deny cases, and approval scoping

**Files:**
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py`
- Create or Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_multi_root_path_execution.py`
- Modify: `tldw_Server_API/tests/Persona/test_persona_ws.py`
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`

**Step 1: Add failing backend mapping tests**

Cover:

- two absolute paths under two allowed workspaces succeed
- relative path stays anchored to the active workspace
- absolute path under an unallowed workspace hard-denies
- absolute path under no trusted workspace hard-denies
- absolute path matching two roots hard-denies
- multi-root request with `cwd_descendants` hard-denies

**Step 2: Add failing approval-scope tests**

Cover:

- approval scope changes when workspace bundle changes
- approval scope changes when normalized path set changes
- trusted-but-unassigned workspace in multi-root mode is deny-only

**Step 3: Add failing persona/UI tests**

Cover:

- hard-deny message for ambiguous workspace match
- hard-deny message for workspace not allowed in multi-root bundle
- approval still renders exact path-set context when only path scope is violated

**Step 4: Run focused tests and confirm failure**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_multi_root_path_execution.py \
  tldw_Server_API/tests/Persona/test_persona_ws.py -k "multi_root or workspace_bundle or path_scope" -v

cd apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx
```

Expected: FAIL.

### Task 2: Add a workspace-bundle resolver and exact path-to-workspace mapping

**Files:**
- Create: `tldw_Server_API/app/services/mcp_hub_multi_root_path_service.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_workspace_root_resolver.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_policy_resolver.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_multi_root_path_execution.py`

**Step 1: Add bundle resolution helpers**

Implement helpers that:

- load the assignment-allowed workspace id bundle
- resolve each workspace id through the correct trust source
- return exact resolved roots
- fail closed on unresolved or ambiguous bundle members

**Step 2: Add path-to-workspace mapping**

Implement mapping rules:

- relative paths resolve against the active workspace only
- absolute paths may match any resolved bundle root
- each path must map to exactly one root

**Step 3: Run focused backend tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_multi_root_path_execution.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py -k "multi_root or workspace_bundle" -v
```

Expected: PASS.

### Task 3: Integrate multi-root enforcement into the path enforcement service

**Files:**
- Modify: `tldw_Server_API/app/services/mcp_hub_path_enforcement_service.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_path_scope_service.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_multi_root_path_execution.py`

**Step 1: Gate multi-root eligibility**

Support multi-root only when:

- tool is path-boundable
- path scope mode is `workspace_root`

Hard deny when:

- mode is `cwd_descendants`
- tool is not path-boundable

**Step 2: Apply per-path enforcement relative to matched roots**

For each mapped path:

- enforce workspace containment using the matched root
- enforce allowlist prefixes relative to the matched root

**Step 3: Keep multi-root membership deny-only**

When any mapped path lands in a trusted-but-unassigned workspace:

- hard deny
- no approval

**Step 4: Run focused runtime tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_multi_root_path_execution.py -v
```

Expected: PASS.

### Task 4: Extend approval scoping and protocol payloads to be bundle-aware

**Files:**
- Modify: `tldw_Server_API/app/services/mcp_hub_approval_service.py`
- Modify: `tldw_Server_API/app/core/MCP_unified/protocol.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_multi_root_path_execution.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py`

**Step 1: Extend scope payload shape**

Add bundle-aware fields:

- `workspace_bundle_ids`
- `workspace_bundle_roots`
- `normalized_paths`
- optional `path_workspace_map`

**Step 2: Extend approval hashing**

Ensure approval scope changes when:

- the workspace bundle changes
- the normalized path set changes

**Step 3: Preserve deny-only cases**

Protocol should continue to hard deny:

- unmatched workspace
- ambiguous match
- unallowed workspace in bundle

**Step 4: Run focused approval tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_multi_root_path_execution.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py -k "approval or bundle or ambiguous" -v
```

Expected: PASS.

### Task 5: Add persona/runtime messaging for multi-root deny and approval cases

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/persona.py`
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- Modify: `tldw_Server_API/tests/Persona/test_persona_ws.py`
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`

**Step 1: Forward multi-root governance details**

Expose bundle-aware path governance payloads through the persona tool-result bridge.

**Step 2: Render deny messages**

Add explicit runtime UI messages for:

- ambiguous workspace match
- workspace not allowed for bundle
- no trusted workspace match

**Step 3: Preserve exact-path approval rendering**

If the workspace bundle is valid but path scope still blocks:

- show approval with exact path-set context

**Step 4: Run focused persona/UI tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Persona/test_persona_ws.py -k "multi_root or workspace_bundle" -v

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
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_multi_root_path_execution.py \
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
  tldw_Server_API/app/services/mcp_hub_multi_root_path_service.py \
  tldw_Server_API/app/services/mcp_hub_path_enforcement_service.py \
  tldw_Server_API/app/services/mcp_hub_workspace_root_resolver.py \
  tldw_Server_API/app/core/MCP_unified/protocol.py \
  tldw_Server_API/app/api/v1/endpoints/persona.py
```

Expected: no new findings.

**Step 4: Update plan status and commit**

Mark all tasks complete and create a checkpoint commit for the slice.
