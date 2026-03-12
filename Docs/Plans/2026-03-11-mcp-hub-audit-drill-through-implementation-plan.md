# MCP Hub Audit Drill-Through Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade the MCP Hub audit view so `Open` jumps to the target tab and automatically opens the existing edit/details UI when supported, with a visible focus fallback otherwise.

**Architecture:** Keep this slice UI-only. Add a page-owned one-shot `McpHubDrillTarget` with `request_id`, derive `edit` vs `focus` client-side from the existing audit `navigate_to` payload, and wire supported tabs to react after their list data is loaded.

**Tech Stack:** React, TypeScript, Ant Design, Vitest

---

## Status

- Task 1: Not Started
- Task 2: Not Started
- Task 3: Not Started
- Task 4: Not Started
- Task 5: Not Started

### Task 1: Add failing UI tests for drill-through behavior

**Files:**
- Modify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/McpHubPage.test.tsx`
- Modify or Create: `apps/packages/ui/src/components/Option/MCPHub/__tests__/PolicyAssignmentsTab.test.tsx`
- Modify or Create: `apps/packages/ui/src/components/Option/MCPHub/__tests__/WorkspaceSetsTab.test.tsx`
- Modify or Create: `apps/packages/ui/src/components/Option/MCPHub/__tests__/SharedWorkspacesTab.test.tsx`
- Modify or Create: `apps/packages/ui/src/components/Option/MCPHub/__tests__/ExternalServersTab.test.tsx`

**Step 1: Extend the page-level test**

Add a failing test that proves:

- audit `Open` creates a new one-shot drill request
- the page switches to the requested tab

**Step 2: Add tab-level failing tests**

Cover:

- assignments auto-open existing editor from a drill target
- workspace sets auto-open existing editor from a drill target
- shared workspaces auto-open existing editor from a drill target
- external servers auto-open managed editor and visibly focus legacy rows

**Step 3: Run focused tests to confirm failure**

Run:

```bash
cd apps/packages/ui && bunx vitest run \
  src/components/Option/MCPHub/__tests__/McpHubPage.test.tsx \
  src/components/Option/MCPHub/__tests__/PolicyAssignmentsTab.test.tsx \
  src/components/Option/MCPHub/__tests__/WorkspaceSetsTab.test.tsx \
  src/components/Option/MCPHub/__tests__/SharedWorkspacesTab.test.tsx \
  src/components/Option/MCPHub/__tests__/ExternalServersTab.test.tsx
```

Expected: FAIL.

### Task 2: Add the shared drill-through contract in MCP Hub page state

**Files:**
- Modify: `apps/packages/ui/src/services/tldw/mcp-hub.ts`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/McpHubPage.tsx`

**Step 1: Add client-side drill target types**

Add:

- `McpHubDrillAction`
- `McpHubDrillTarget`

Include:

- `tab`
- `object_kind`
- `object_id`
- `action`
- `request_id`

**Step 2: Extend `McpHubPage` state**

Store:

- `activeTab`
- `drillTarget`

Derive `action` client-side from `navigate_to`:

- `edit` for supported editable tabs/object kinds
- `focus` otherwise

**Step 3: Add one-shot acknowledgment plumbing**

Pass:

- `drillTarget`
- `onDrillHandled`

to supported tabs.

Only clear the drill target when `request_id` matches the active one.

**Step 4: Run page-level tests**

Run:

```bash
cd apps/packages/ui && bunx vitest run \
  src/components/Option/MCPHub/__tests__/McpHubPage.test.tsx
```

Expected: PASS.

### Task 3: Wire full auto-open support into editable MCP Hub tabs

**Files:**
- Modify: `apps/packages/ui/src/components/Option/MCPHub/PolicyAssignmentsTab.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/WorkspaceSetsTab.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/SharedWorkspacesTab.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/ExternalServersTab.tsx`

**Step 1: Add drill-through props**

For each supported tab, add optional props:

- `drillTarget?: McpHubDrillTarget | null`
- `onDrillHandled?: (requestId: number) => void`

**Step 2: Handle drill targets after data load**

In each tab:

- wait until rows are loaded
- match `object_kind` + `object_id`
- open the existing editor/details form
- call `onDrillHandled(requestId)` only after successful open

**Step 3: Preserve existing local edit flows**

Reuse each tab’s current edit/open path instead of creating new UI:

- assignments -> existing assignment editor
- workspace sets -> existing edit form
- shared workspaces -> existing edit form
- external servers -> existing managed editor/details form

**Step 4: Run focused tab tests**

Run:

```bash
cd apps/packages/ui && bunx vitest run \
  src/components/Option/MCPHub/__tests__/PolicyAssignmentsTab.test.tsx \
  src/components/Option/MCPHub/__tests__/WorkspaceSetsTab.test.tsx \
  src/components/Option/MCPHub/__tests__/SharedWorkspacesTab.test.tsx \
  src/components/Option/MCPHub/__tests__/ExternalServersTab.test.tsx
```

Expected: PASS.

### Task 4: Add fallback focus behavior for non-editable targets

**Files:**
- Modify: `apps/packages/ui/src/components/Option/MCPHub/ExternalServersTab.tsx`
- Optionally Modify: `apps/packages/ui/src/components/Option/MCPHub/policyHelpers.ts`
- Modify: relevant UI tests above

**Step 1: Add a transient focused-row state**

Implement a lightweight fallback visual state:

- `focusedObjectId`

Use it when:

- the drill target is valid for the tab
- but direct edit/details open is unsupported

**Step 2: Implement legacy external server fallback**

For legacy external servers:

- switch to `Credentials`
- visibly focus/highlight the row
- do not try to open the managed editor form
- acknowledge the drill request

**Step 3: Run focused fallback tests**

Run:

```bash
cd apps/packages/ui && bunx vitest run \
  src/components/Option/MCPHub/__tests__/ExternalServersTab.test.tsx
```

Expected: PASS.

### Task 5: Final verification, docs update, and commit

**Files:**
- Modify: `Docs/Plans/2026-03-11-mcp-hub-audit-drill-through-design.md`
- Modify: `Docs/Plans/2026-03-11-mcp-hub-audit-drill-through-implementation-plan.md`

**Step 1: Run focused UI verification**

Run:

```bash
cd apps/packages/ui && bunx vitest run \
  src/components/Option/MCPHub/__tests__/McpHubPage.test.tsx \
  src/components/Option/MCPHub/__tests__/PolicyAssignmentsTab.test.tsx \
  src/components/Option/MCPHub/__tests__/WorkspaceSetsTab.test.tsx \
  src/components/Option/MCPHub/__tests__/SharedWorkspacesTab.test.tsx \
  src/components/Option/MCPHub/__tests__/ExternalServersTab.test.tsx
```

Expected: PASS.

**Step 2: Run broader MCP Hub UI slice**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/components/Option/MCPHub/__tests__
```

Expected: PASS.

**Step 3: Update doc status**

Set:

- design doc status to `Implemented`
- all task statuses in this plan to `Complete`

**Step 4: Commit**

```bash
git add \
  Docs/Plans/2026-03-11-mcp-hub-audit-drill-through-design.md \
  Docs/Plans/2026-03-11-mcp-hub-audit-drill-through-implementation-plan.md \
  apps/packages/ui/src/components/Option/MCPHub/McpHubPage.tsx \
  apps/packages/ui/src/components/Option/MCPHub/PolicyAssignmentsTab.tsx \
  apps/packages/ui/src/components/Option/MCPHub/WorkspaceSetsTab.tsx \
  apps/packages/ui/src/components/Option/MCPHub/SharedWorkspacesTab.tsx \
  apps/packages/ui/src/components/Option/MCPHub/ExternalServersTab.tsx \
  apps/packages/ui/src/services/tldw/mcp-hub.ts
git commit -m "feat: add MCP Hub audit drill-through"
```
