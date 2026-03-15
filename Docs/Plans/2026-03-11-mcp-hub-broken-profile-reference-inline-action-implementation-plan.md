# MCP Hub Broken Profile Reference Inline Action Implementation Plan

**Goal:** Add dedicated broken assignment `profile_id` audit findings and one safe inline action to clear the broken permission-profile reference.

**Architecture:** Extend the audit feed with a non-throwing permission-profile reference inspector in the MCP Hub service layer, reuse the existing `broken_object_reference` finding family with structured details, and add one UI-only deterministic action that maps to `updatePolicyAssignment(id, { profile_id: null })`.

**Tech Stack:** FastAPI service layer, existing MCP Hub audit feed, React, TypeScript, Vitest, pytest, Bandit

**Status:** Complete

---

### Task 1: Add Red Tests For Broken Profile Reference Findings

**Status:** Complete

**Goal:** Prove the backend does not yet emit broken `profile_id` findings.

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/mcp-hub-tool-permissions/tldw_Server_API/tests/MCP_unified/test_mcp_hub_audit_findings.py`

**Steps:**
1. Add audit-finding tests for assignment `profile_id` references with:
   - missing profile
   - inactive profile
   - scope-incompatible profile
2. Assert:
   - `finding_type == "broken_object_reference"`
   - `details.reference_field == "profile_id"`
   - `details.reference_object_kind == "permission_profile"`
3. Run the focused backend audit test to confirm RED.

**Run:**
```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_unified/test_mcp_hub_audit_findings.py -v
```

### Task 2: Add Non-Throwing Permission Profile Reference Inspection

**Status:** Complete

**Goal:** Implement the new structured backend finding input.

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/mcp-hub-tool-permissions/tldw_Server_API/app/services/mcp_hub_service.py`

**Steps:**
1. Add `inspect_permission_profile_reference(...)`.
2. Reuse same-scope-or-parent compatibility checks.
3. Return structured `missing/inactive/scope_incompatible` result objects.
4. Extend audit finding composition for assignments to emit the new broken-reference finding.
5. Keep the check direct-reference-only.

**Run:**
```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_unified/test_mcp_hub_audit_findings.py -v
```

### Task 3: Add Red UI Tests For The Inline Clear Action

**Status:** Complete

**Goal:** Prove the UI does not yet offer the new action.

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/mcp-hub-tool-permissions/apps/packages/ui/src/components/Option/MCPHub/__tests__/governanceAuditHelpers.test.ts`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/mcp-hub-tool-permissions/apps/packages/ui/src/components/Option/MCPHub/__tests__/GovernanceAuditTab.test.tsx`

**Steps:**
1. Add helper test for:
   - eligible assignment broken profile reference -> `clear_permission_profile_reference`
2. Add audit-tab interaction tests for:
   - button render
   - correct `updatePolicyAssignment(..., { profile_id: null })` mutation
   - success/error messages
3. Run focused UI tests to confirm RED.

**Run:**
```bash
bunx vitest run src/components/Option/MCPHub/__tests__/GovernanceAuditTab.test.tsx src/components/Option/MCPHub/__tests__/governanceAuditHelpers.test.ts
```

### Task 4: Implement The UI Action

**Status:** Complete

**Goal:** Wire the new structured finding to one deterministic mutation.

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/mcp-hub-tool-permissions/apps/packages/ui/src/components/Option/MCPHub/governanceAuditHelpers.ts`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/mcp-hub-tool-permissions/apps/packages/ui/src/components/Option/MCPHub/GovernanceAuditTab.tsx`

**Steps:**
1. Extend the inline-action union with `clear_permission_profile_reference`.
2. Gate eligibility strictly on structured broken-reference details.
3. Execute `updatePolicyAssignment(object_id, { profile_id: null })`.
4. Add assignment-specific confirmation/success/error copy.
5. Keep existing actions unchanged.

**Run:**
```bash
bunx vitest run src/components/Option/MCPHub/__tests__/GovernanceAuditTab.test.tsx src/components/Option/MCPHub/__tests__/governanceAuditHelpers.test.ts
```

### Task 5: Full Verification And Security Check

**Status:** Complete

**Goal:** Verify the slice and touched backend scope cleanly.

**Run:**
```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_unified/test_mcp_hub_audit_findings.py -v
bunx vitest run src/components/Option/MCPHub/__tests__
source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/services/mcp_hub_service.py -f json -o /tmp/bandit_broken_profile_reference.json
```

### Task 6: Mark Docs Implemented And Commit

**Status:** Complete

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/mcp-hub-tool-permissions/Docs/Plans/2026-03-11-mcp-hub-broken-profile-reference-inline-action-design.md`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/mcp-hub-tool-permissions/Docs/Plans/2026-03-11-mcp-hub-broken-profile-reference-inline-action-implementation-plan.md`

**Steps:**
1. Flip design status to `Implemented`.
2. Mark plan/tasks `Complete`.
3. Commit with:
   - `feat: add broken profile inline remediation`
