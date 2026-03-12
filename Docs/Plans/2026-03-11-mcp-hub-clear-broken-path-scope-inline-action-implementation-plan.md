# MCP Hub Clear Broken Path Scope Inline Action Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add one safe audit inline action that clears broken `path_scope_object_id` references from assignments and permission profiles.

**Architecture:** Extend the current client-side audit action helper with a second discriminated action kind, keep eligibility strictly structured around `broken_object_reference` findings, and reuse the existing MCP Hub update clients to send an exact `{ path_scope_object_id: null }` mutation. This remains a UI-only slice with audit-refresh-on-success semantics.

**Tech Stack:** React, TypeScript, Ant Design, Vitest, existing MCP Hub client service helpers

---

### Task 1: Add Red Tests For The New Action

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/mcp-hub-tool-permissions/apps/packages/ui/src/components/Option/MCPHub/__tests__/governanceAuditHelpers.test.ts`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/mcp-hub-tool-permissions/apps/packages/ui/src/components/Option/MCPHub/__tests__/GovernanceAuditTab.test.tsx`

**Step 1: Add helper tests for action eligibility**

Write failing tests that expect:
- an assignment `broken_object_reference` with `reference_field=path_scope_object_id` returns a `clear_path_scope_reference` action
- a permission profile `broken_object_reference` with the same field returns the same action kind
- a broken workspace-set reference still returns `null`

**Step 2: Run helper tests to confirm RED**

Run:

```bash
bunx vitest run src/components/Option/MCPHub/__tests__/governanceAuditHelpers.test.ts
```

Expected: fail because `buildAuditInlineAction(...)` only returns `deactivate_external_server`

**Step 3: Add audit tab interaction tests**

Write failing tests that expect:
- `Clear broken path scope` button renders for assignment broken-reference findings
- `Clear broken path scope` button renders for permission-profile broken-reference findings
- clicking the button calls the correct existing client mutation with `{ path_scope_object_id: null }`
- success and failure messages are object-kind-specific

**Step 4: Run focused audit tests to confirm RED**

Run:

```bash
bunx vitest run src/components/Option/MCPHub/__tests__/GovernanceAuditTab.test.tsx src/components/Option/MCPHub/__tests__/governanceAuditHelpers.test.ts
```

Expected: fail because the new action kind and execution path do not exist yet

**Step 5: Commit**

Do not commit yet. Continue to Task 2 once the red tests fail as expected.

### Task 2: Extend The Audit Action Helper

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/mcp-hub-tool-permissions/apps/packages/ui/src/components/Option/MCPHub/governanceAuditHelpers.ts`

**Step 1: Convert the action type into a discriminated union**

Add a second action kind:
- `clear_path_scope_reference`

Include:
- `object_kind`
- `object_id`
- confirm text
- success text
- error text

**Step 2: Implement strict structured eligibility**

Update `buildAuditInlineAction(...)` so the new action is returned only when:
- `finding_type === "broken_object_reference"`
- `details.reference_field === "path_scope_object_id"`
- `details.reference_object_kind === "path_scope_object"`
- consumer is `policy_assignment` or `permission_profile`

**Step 3: Preserve current behavior**

Leave the existing `Deactivate server` logic intact.

**Step 4: Run helper tests**

Run:

```bash
bunx vitest run src/components/Option/MCPHub/__tests__/governanceAuditHelpers.test.ts
```

Expected: helper tests pass, tab interaction tests still fail

**Step 5: Commit**

Do not commit yet. Continue to Task 3.

### Task 3: Wire The New Action Into GovernanceAuditTab

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/mcp-hub-tool-permissions/apps/packages/ui/src/components/Option/MCPHub/GovernanceAuditTab.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/mcp-hub-tool-permissions/apps/packages/ui/src/services/tldw/mcp-hub.ts`

**Step 1: Import the existing client update functions**

Use:
- `updatePolicyAssignment(...)`
- `updatePermissionProfile(...)`

Do not add any new backend endpoint.

**Step 2: Extend `_runInlineAction(...)`**

Handle:
- `deactivate_external_server`
- `clear_path_scope_reference`

Mutation mapping:
- assignment -> `updatePolicyAssignment(id, { path_scope_object_id: null })`
- profile -> `updatePermissionProfile(id, { path_scope_object_id: null })`

**Step 3: Use action-provided copy**

Show success/error messages from the action descriptor, not hardcoded strings.

**Step 4: Preserve refresh semantics**

After success:
- refetch audit findings
- show success feedback
- clear pending state

After failure:
- keep the finding visible
- show error feedback

**Step 5: Run focused audit tests**

Run:

```bash
bunx vitest run src/components/Option/MCPHub/__tests__/GovernanceAuditTab.test.tsx src/components/Option/MCPHub/__tests__/governanceAuditHelpers.test.ts
```

Expected: all focused tests pass

**Step 6: Commit**

Do not commit yet. Continue to Task 4.

### Task 4: Run Wider MCP Hub UI Verification

**Files:**
- No code changes expected

**Step 1: Run the full MCP Hub UI suite**

Run:

```bash
bunx vitest run src/components/Option/MCPHub/__tests__
```

Expected: all MCP Hub UI tests pass

**Step 2: Review for regressions**

Confirm:
- existing `Deactivate server` behavior still works
- audit export/correlation behavior still works
- grouped finding order remains stable

**Step 3: Commit**

Do not commit yet. Continue to Task 5.

### Task 5: Mark Docs Implemented And Commit

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/mcp-hub-tool-permissions/Docs/Plans/2026-03-11-mcp-hub-clear-broken-path-scope-inline-action-design.md`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/mcp-hub-tool-permissions/Docs/Plans/2026-03-11-mcp-hub-clear-broken-path-scope-inline-action-implementation-plan.md`

**Step 1: Update doc statuses**

Set:
- design doc -> `Implemented`
- plan doc -> `Complete`
- task statuses -> `Complete`

**Step 2: Stage touched files**

Stage:
- `governanceAuditHelpers.ts`
- `GovernanceAuditTab.tsx`
- `mcp-hub.ts` if touched
- both test files
- both docs

**Step 3: Commit**

```bash
git add apps/packages/ui/src/components/Option/MCPHub/governanceAuditHelpers.ts \
  apps/packages/ui/src/components/Option/MCPHub/GovernanceAuditTab.tsx \
  apps/packages/ui/src/services/tldw/mcp-hub.ts \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/GovernanceAuditTab.test.tsx \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/governanceAuditHelpers.test.ts \
  Docs/Plans/2026-03-11-mcp-hub-clear-broken-path-scope-inline-action-design.md \
  Docs/Plans/2026-03-11-mcp-hub-clear-broken-path-scope-inline-action-implementation-plan.md

git commit -m "feat: add broken path scope inline remediation"
```

**Step 4: Confirm clean state**

Run:

```bash
git status --short
```

Expected: only the unrelated pre-existing untracked audit zip remains
