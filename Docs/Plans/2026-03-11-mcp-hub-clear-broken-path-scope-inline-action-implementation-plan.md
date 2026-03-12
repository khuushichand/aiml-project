# MCP Hub Clear Broken Path Scope Inline Action Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add one safe inline audit action that clears broken `path_scope_object_id` references from assignments and permission profiles.

**Architecture:** Extend the existing client-side audit inline action helper with a new discriminated action kind and reuse the existing MCP Hub update clients to send an exact `path_scope_object_id: null` mutation. Keep the slice UI-only, refresh the audit feed after mutation, and preserve the existing audit-driven workflow.

**Tech Stack:** React, TypeScript, Ant Design, Vitest, existing MCP Hub service client helpers

---

### Task 1: Add Red Tests For The New Inline Action

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/mcp-hub-tool-permissions/apps/packages/ui/src/components/Option/MCPHub/__tests__/governanceAuditHelpers.test.ts`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/mcp-hub-tool-permissions/apps/packages/ui/src/components/Option/MCPHub/__tests__/GovernanceAuditTab.test.tsx`

**Step 1: Write the failing helper tests**

Add tests that expect:
- `broken_object_reference` on a `policy_assignment` with `reference_field=path_scope_object_id` returns a `clear_path_scope_reference` action descriptor
- the same for a `permission_profile`
- a `workspace_set_object_id` broken reference still returns `null`

**Step 2: Run helper tests to verify they fail**

Run:

```bash
bunx vitest run src/components/Option/MCPHub/__tests__/governanceAuditHelpers.test.ts
```

Expected: fail because `buildAuditInlineAction(...)` only supports `deactivate_external_server`

**Step 3: Write the failing tab tests**

Add tests that expect:
- the audit row renders `Clear broken path scope` for eligible assignment findings
- clicking it calls the assignment update client with `{ path_scope_object_id: null }`
- the same for permission profiles with the profile update client

**Step 4: Run the focused UI tests to verify they fail**

Run:

```bash
bunx vitest run src/components/Option/MCPHub/__tests__/GovernanceAuditTab.test.tsx src/components/Option/MCPHub/__tests__/governanceAuditHelpers.test.ts
```

Expected: fail because the new action kind and mutation path do not exist yet

**Step 5: Commit**

Do not commit yet. Continue to Task 2 once the red tests fail as expected.

### Task 2: Extend The Audit Action Helper

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/mcp-hub-tool-permissions/apps/packages/ui/src/components/Option/MCPHub/governanceAuditHelpers.ts`

**Step 1: Add the new action union shape**

Extend `GovernanceAuditInlineAction` with:
- `kind: "clear_path_scope_reference"`
- `object_kind`
- `object_id`
- object-kind-specific confirm/success/error copy

**Step 2: Implement deterministic eligibility**

Update `buildAuditInlineAction(...)` so it returns the new action only when:
- `finding_type === "broken_object_reference"`
- `reference_field === "path_scope_object_id"`
- `reference_object_kind === "path_scope_object"`
- consumer is `policy_assignment` or `permission_profile`

**Step 3: Keep all other findings unchanged**

Existing `Deactivate server` logic should stay intact.

**Step 4: Run helper tests**

Run:

```bash
bunx vitest run src/components/Option/MCPHub/__tests__/governanceAuditHelpers.test.ts
```

Expected: helper tests pass, tab tests still fail

**Step 5: Commit**

Do not commit yet. Continue to Task 3.

### Task 3: Wire The New Action Into GovernanceAuditTab

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/mcp-hub-tool-permissions/apps/packages/ui/src/components/Option/MCPHub/GovernanceAuditTab.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/mcp-hub-tool-permissions/apps/packages/ui/src/services/tldw/mcp-hub.ts`

**Step 1: Import and use the existing update clients**

Ensure the tab can call:
- `updatePolicyAssignment(...)`
- `updatePermissionProfile(...)`

**Step 2: Extend `_runInlineAction(...)`**

Handle:
- `deactivate_external_server`
- `clear_path_scope_reference`

For `clear_path_scope_reference`:
- assignment -> `updatePolicyAssignment(id, { path_scope_object_id: null })`
- profile -> `updatePermissionProfile(id, { path_scope_object_id: null })`

**Step 3: Use object-kind-specific copy**

Show the exact success/error message from the action descriptor.

**Step 4: Keep the refresh behavior unchanged**

After success:
- call `loadAuditFindings()`
- clear pending state
- show success feedback

After failure:
- keep current row visible
- show error feedback

**Step 5: Run focused UI tests**

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

Verify that:
- existing `Deactivate server` behavior still works
- audit exports still work
- grouped findings still render in fixed order

**Step 3: Commit**

Do not commit yet. Continue to Task 5.

### Task 5: Mark Docs Implemented And Commit

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/mcp-hub-tool-permissions/Docs/Plans/2026-03-11-mcp-hub-clear-broken-path-scope-inline-action-design.md`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/mcp-hub-tool-permissions/Docs/Plans/2026-03-11-mcp-hub-clear-broken-path-scope-inline-action-implementation-plan.md`

**Step 1: Update document statuses**

Set:
- design doc -> `Implemented`
- plan doc task statuses -> `Complete`

**Step 2: Stage the touched files**

Stage:
- helper
- audit tab
- any touched client types
- test files
- the two docs

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
