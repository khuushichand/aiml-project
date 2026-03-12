# MCP Hub Audit Drill-Through Design

Date: 2026-03-11
Status: Approved for planning

## Goal

Upgrade the MCP Hub `Audit` tab so `Open` does more than switch tabs. The new
behavior should jump to the target MCP Hub tab and automatically open the
target object's existing edit/details UI when one exists.

This slice remains intentionally narrow:

- UI-only
- reuse existing edit forms/details surfaces
- one-shot MCP Hub-local drill-through intent
- fallback to focus/highlight for non-editable targets

## Scope

This slice covers:

- a formal MCP Hub-local drill-through state contract
- automatic edit/details opening for supported tabs
- fallback row focus/highlight for unsupported or non-editable targets
- audit `Open` continuing to work through the existing audit feed

This slice does not cover:

- backend audit finding changes
- route/query-param deep links
- a shared global MCP Hub details drawer
- new editors or remediation actions

## Review Corrections

### 1. Use prop-driven synchronization, not imperative handles

The relevant MCP Hub tabs are plain function components with local state such
as `editingId`, `createOpen`, or selected-row state. They do not expose an
imperative edit API today.

This slice therefore uses page-owned drill-through state passed into tabs as
props. Each tab reacts in `useEffect` after its data is loaded.

### 2. Drill-through needs a one-shot `request_id`

Opening the same object twice in a row from the audit tab must still trigger
tab handling. A plain `{tab, object_id}` payload is not enough because React
may treat repeated identical state as unchanged.

The drill-through contract therefore includes a monotonically changing
`request_id`.

### 3. Tabs must defer handling until data is ready

Tabs like `PolicyAssignmentsTab`, `WorkspaceSetsTab`, `SharedWorkspacesTab`,
and `ExternalServersTab` fetch list data asynchronously. If a drill target is
cleared before the tab has matching rows loaded, the request is lost.

Tabs should therefore:

- keep the incoming drill target until their rows are loaded
- handle it only when the matching row can be found
- call `onDrillHandled` only after successful open/focus or an intentional
  fallback decision

### 4. Fallback focus behavior must be visible

For targets without a programmatic edit/details path, the UI should not silently
ignore the drill target. The fallback behavior is:

- switch to the correct tab
- visibly focus/highlight the matching row
- clear the drill target once the fallback is applied

This is especially important for legacy external server rows.

### 5. Keep this slice UI-only

The current audit `navigate_to` payload already includes:

- `tab`
- `object_kind`
- `object_id`

This is enough for the first drill-through enhancement. `action` can be derived
client-side:

- `edit` for editable object kinds/tabs
- `focus` for fallback-only targets

No backend contract change is required in this slice.

## Drill-Through Model

`McpHubPage` should own one drill-through state object:

- `tab`
- `object_kind`
- `object_id`
- `action`
- `request_id`

Recommended types:

- `McpHubDrillAction`
  - `edit`
  - `focus`
- `McpHubDrillTarget`
  - `tab`
  - `object_kind`
  - `object_id`
  - `action`
  - `request_id`

Flow:

1. `GovernanceAuditTab` emits `onOpen(navigateTarget)`.
2. `McpHubPage` derives the desired action and creates a fresh `request_id`.
3. `McpHubPage` sets `activeTab` and passes `drillTarget` to all tabs.
4. The active tab handles the request once its data is ready.
5. The tab invokes `onDrillHandled(request_id)` after success or an intentional
   fallback.
6. `McpHubPage` clears the matching one-shot target.

## Initial Tab Support

### Full auto-open support

These tabs already have a clear edit/details surface and should auto-open it:

- `Assignments`
- `Workspace Sets`
- `Shared Workspaces`
- `Credentials` for managed external servers

### Fallback focus support

These tabs should switch and visually focus/highlight the row when direct
auto-open is unavailable or unsupported:

- `Credentials` for legacy external servers
- `Profiles`
- `Path Scopes`
- `Catalog`
- `Approvals`

The first implementation only needs to wire the tabs already used by current
audit findings:

- `Assignments`
- `Workspace Sets`
- `Shared Workspaces`
- `Credentials`

## Per-Tab Behavior

### Assignments

When `drillTarget.tab === "assignments"` and the object matches a policy
assignment id:

- wait for assignments to load
- select the matching assignment
- open the existing assignment editor
- acknowledge the drill request

### Workspace Sets

When the target matches a workspace-set id:

- wait for rows to load
- open the existing edit form
- acknowledge the drill request

### Shared Workspaces

When the target matches a shared workspace id:

- wait for rows to load
- open the existing edit form
- acknowledge the drill request

### Credentials

For managed external server findings:

- wait for rows to load
- open the existing managed server editor/details form
- acknowledge the drill request

For legacy external server findings:

- wait for rows to load
- apply visible row focus/highlight
- acknowledge the drill request

## Fallback Focus Contract

Tabs that cannot directly open a form should still make the request visible.

Minimum v1 behavior:

- maintain a transient `focusedObjectId`
- render a small emphasis marker for the matching row
  - e.g. `Tag`, `Alert`, border accent, or helper text
- clear/replace that focus state on the next drill request

This is intentionally lightweight and tab-local.

## Testing

### UI tests

Add coverage for:

- `McpHubPage`
  - `Open` creates a one-shot drill target and switches tabs
- `PolicyAssignmentsTab`
  - drill target opens the assignment editor
- `WorkspaceSetsTab`
  - drill target opens the workspace-set editor
- `SharedWorkspacesTab`
  - drill target opens the shared-workspace editor
- `ExternalServersTab`
  - managed target auto-opens editor
  - legacy target visibly focuses row

### Regression

Confirm:

- repeated `Open` on the same object still works because of `request_id`
- tabs do not clear unhandled targets before data loads
- switching tabs manually does not reopen stale drill requests

## Risks

Main risks:

- one-shot targets not being cleared correctly
- tabs trying to handle drill requests before list data is available
- over-coupling every MCP Hub tab to a generic navigation framework

Mitigations:

- use `request_id`
- require tab-side acknowledgment
- keep the contract local and minimal

## Out Of Scope

- route-level deep-linking
- backend `navigate_to` expansion
- a new shared details drawer
- audit remediation actions
