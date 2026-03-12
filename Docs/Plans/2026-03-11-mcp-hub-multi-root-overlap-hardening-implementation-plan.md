# MCP Hub Multi-Root Overlap Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add assignment-scoped save-time validation so multi-root-eligible assignments cannot use overlapping or unresolved workspace bundles.

**Architecture:** Reuse the existing effective policy and workspace trust-source model, add an assignment readiness validator in the MCP Hub service/write path, validate the active workspace source only, and return structured conflict payloads the assignment UI can render directly.

**Tech Stack:** FastAPI, MCP Hub service layer, MCP Hub policy/workspace resolvers, React MCP Hub assignment editor, pytest, Vitest, Bandit

---

## Status

- Task 1: Complete
- Task 2: Complete
- Task 3: Complete
- Task 4: Complete
- Task 5: Complete
- Task 6: Complete

### Task 1: Add failing backend and UI tests for multi-root assignment readiness validation

**Files:**
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py`
- Create or Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_multi_root_assignment_validation.py`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/PolicyAssignmentsTab.test.tsx`

**Step 1: Write failing backend readiness tests**

Cover:

- inline workspace source plus effective `workspace_root` rejects overlapping roots
- named workspace source plus effective `workspace_root` rejects overlapping roots
- unresolved workspace id rejects save
- identical canonical roots under different workspace ids reject save
- disjoint roots pass

**Step 2: Write failing effective-mode tests**

Cover:

- same workspace bundle under `cwd_descendants` does not trigger overlap rejection
- inherited `workspace_root` from profile/path-scope object still triggers validation

**Step 3: Write failing UI tests**

Cover:

- assignment editor shows structured overlap error from API
- assignment editor shows unresolved-workspace error from API
- switching workspace source preserves inactive data and validates only the active source

**Step 4: Run focused tests to confirm failure**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_multi_root_assignment_validation.py -v

cd apps/packages/ui && bunx vitest run \
  src/components/Option/MCPHub/__tests__/PolicyAssignmentsTab.test.tsx
```

Expected: FAIL.

### Task 2: Add an assignment readiness validator that uses effective path mode and active workspace source

**Files:**
- Modify: `tldw_Server_API/app/services/mcp_hub_service.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_policy_resolver.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_workspace_root_resolver.py`
- Create or Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_multi_root_assignment_validation.py`

**Step 1: Add a backend helper**

Add a helper like:

- `validate_multi_root_assignment_readiness(...)`

It should:

- resolve the active workspace source only
- reconstruct or resolve the effective path mode
- skip overlap checks unless effective mode is `workspace_root` and bundle size is `>1`
- resolve workspace roots through the effective trust source

**Step 2: Reuse canonical containment semantics**

Implement overlap detection using canonical roots and ancestry checks consistent
with existing path enforcement behavior.

**Step 3: Return structured validation payloads**

Return structured failures with:

- `code`
- `message`
- `workspace_source_mode`
- `workspace_trust_source`
- `conflicting_workspace_ids`
- `conflicting_workspace_roots`
- `unresolved_workspace_ids`

**Step 4: Run focused backend tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_multi_root_assignment_validation.py -v
```

Expected: PASS.

### Task 3: Wire validation into every assignment mutation path that can change active source or eligibility

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_service.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py`
- Modify or Create: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_multi_root_assignment_validation.py`

**Step 1: Run validation on assignment create/update**

Ensure assignment row writes validate:

- active workspace source mode
- active workspace members
- effective path mode

**Step 2: Run validation after inline workspace membership sync**

Ensure inline workspace membership writes cannot bypass validation.

**Step 3: Run validation on named workspace source changes**

Ensure switching:

- `workspace_source_mode`
- `workspace_set_object_id`

also triggers validation against the active source only.

**Step 4: Keep inactive source data preserved**

Do not delete or rewrite inactive inline rows or inactive named-source wiring
when validation fails.

**Step 5: Run focused API tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_multi_root_assignment_validation.py -k "assignment and workspace" -v
```

Expected: PASS.

### Task 4: Surface structured validation failures in the MCP Hub assignment editor

**Files:**
- Modify: `apps/packages/ui/src/components/Option/MCPHub/PolicyAssignmentsTab.tsx`
- Modify: `apps/packages/ui/src/services/tldw/mcp-hub.ts`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/PolicyAssignmentsTab.test.tsx`

**Step 1: Preserve active-source-only editing behavior**

Keep:

- named vs inline workspace source selection
- inactive source data preserved in form state

**Step 2: Surface backend validation payloads**

Render structured overlap and unresolved-workspace errors near workspace source
controls, without collapsing to a generic toast-only error.

**Step 3: Keep source switching reversible**

Ensure switching back from named to inline restores inline rows already kept in
state/storage.

**Step 4: Run focused UI tests**

Run:

```bash
cd apps/packages/ui && bunx vitest run \
  src/components/Option/MCPHub/__tests__/PolicyAssignmentsTab.test.tsx
```

Expected: PASS.

### Task 5: Add regression coverage for inherited path mode and trust-source compatibility

**Files:**
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py`
- Modify or Create: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_multi_root_assignment_validation.py`

**Step 1: Add inherited effective-path-mode tests**

Cover assignments that become multi-root-eligible because `workspace_root` is
inherited from:

- profile inline policy
- profile path-scope object
- assignment path-scope object

**Step 2: Add trust-source compatibility tests**

Cover:

- user-local active source resolves via user-local trust source
- shared-registry active source resolves via shared-registry trust source
- mismatched trust source yields unresolved-workspace validation error

**Step 3: Run focused regression tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_multi_root_assignment_validation.py -k "effective or trust or overlap" -v
```

Expected: PASS.

### Task 6: Final verification, Bandit, docs touch-up, and commit

**Files:**
- Modify: touched docs if implementation details drift

**Step 1: Run final focused backend verification**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_multi_root_assignment_validation.py -v
```

Expected: PASS.

**Step 2: Run final focused UI verification**

Run:

```bash
cd apps/packages/ui && bunx vitest run \
  src/components/Option/MCPHub/__tests__/PolicyAssignmentsTab.test.tsx
```

Expected: PASS.

**Step 3: Run Bandit on touched backend scope**

Run:

```bash
source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/services/mcp_hub_service.py \
  tldw_Server_API/app/services/mcp_hub_policy_resolver.py \
  tldw_Server_API/app/services/mcp_hub_workspace_root_resolver.py \
  tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py
```

Expected: no new findings.

**Step 4: Update plan status and commit**

Run:

```bash
git add Docs/Plans/2026-03-11-mcp-hub-multi-root-overlap-hardening-design.md \
        Docs/Plans/2026-03-11-mcp-hub-multi-root-overlap-hardening-implementation-plan.md \
        <touched backend files> <touched tests> <touched UI files>
git commit -m "feat: harden multi-root assignment validation"
```

Expected: clean commit with verified tests.
