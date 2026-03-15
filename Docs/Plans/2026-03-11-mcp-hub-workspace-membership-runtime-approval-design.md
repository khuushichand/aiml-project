# MCP Hub Workspace Membership Runtime Approval Design

Date: 2026-03-11
Status: Implemented

## Goal

Allow narrow runtime approval for a trusted `workspace_id` that is resolvable
through the required trust source but excluded from the selected assignment
workspace membership.

This slice keeps the trust boundary intact:

- unresolvable or untrusted workspaces remain hard deny
- approval never mutates stored workspace membership
- approval applies only to the exact `tool + workspace_id + assignment + trust source`

## Scope

This slice covers:

- tool-specific runtime approval for trusted-but-unassigned workspaces
- hard deny for unresolvable workspaces under the required trust source
- exact approval scoping for workspace membership exceptions
- persona/runtime UI messaging for workspace approval vs hard deny

This slice does not cover:

- persistent mutation of assignment workspace membership
- assignment-wide or workspace-set-wide approvals
- approval for untrusted or unresolvable workspaces
- multi-root execution

## Current Gap

The branch now has:

- user-local and shared-registry workspace trust sources
- reusable inline and named workspace membership sources
- deny-only `workspace_not_allowed_for_assignment`

What is still missing is a narrow runtime escape hatch when:

- the active `workspace_id` is already trusted and resolvable
- but the selected assignment does not include it

Today the runtime hard-denies that case, which is safer than broadening the
stored policy but still too rigid for controlled temporary use.

## Review Corrections

### 1. Trust-source resolution must happen before membership comparison

Current path enforcement checks assignment membership before it looks at
resolver failure state. That can misclassify an unresolvable workspace as
`workspace_not_allowed_for_assignment`.

This slice requires a strict order:

1. resolve active workspace through the required trust source
2. if resolution fails, hard deny
3. only then compare against assignment membership
4. if trusted but not assigned, evaluate runtime approval

### 2. Protocol must stop hard-denying all workspace membership misses

The current protocol special-cases `workspace_not_allowed_for_assignment` into
an immediate `GovernanceDeniedError`.

This slice changes that behavior:

- `workspace_unresolvable_for_trust_source`
  - deny-only
- `workspace_not_allowed_but_trusted`
  - approval candidate

That means the protocol must explicitly route the second case into the existing
runtime approval path instead of denying before approval evaluation.

### 3. Approval scope must include assignment and trust-source identity

The current approval scope hash does not include assignment identity or
workspace trust source.

For this slice, workspace approval scope must include:

- `workspace_id`
- `selected_assignment_id`
- `workspace_source_mode`
- `selected_workspace_trust_source`
- `tool_name`

This ensures approval reuse does not leak across:

- different assignments
- different trust models
- different tools using the same workspace id

### 4. Persona bridge must forward workspace/path governance context

The current persona WebSocket bridge forwards `approval` and
`governance.external_access`, but not path/workspace governance payloads.

This slice requires a forwarded workspace/path governance payload so the
runtime UI can distinguish:

- `trusted but not allowed by assignment`
- `unresolvable for trust source`

without overloading the current external-only context shape.

### 5. Persona UI needs a workspace-specific approval/deny renderer

The current persona approval UI only understands external credential context.

This slice adds a workspace/path governance UI contract that can render:

- trusted denied `workspace_id`
- trust source
- assignment context
- deny-only messaging when the workspace cannot be resolved through the
  required trust source

## Runtime Model

This slice divides workspace membership outcomes into three classes.

### Allow

The active `workspace_id`:

- resolves through the required trust source
- is included in the selected assignment membership source

Runtime continues into existing path-scope and allowlist enforcement.

### Approval Required

The active `workspace_id`:

- resolves through the required trust source
- is not included in the selected assignment membership source

Approval unit:

- exact `tool_name`
- exact denied `workspace_id`
- exact `selected_assignment_id`
- exact `selected_workspace_trust_source`

This is a temporary runtime exception only. It does not alter stored assignment
membership.

### Deny

The active `workspace_id`:

- cannot be resolved through the required trust source
- or fails trust-source compatibility entirely

This remains a hard deny and is never approvable.

## Architecture

The implementation stays on the existing path/workspace seam.

Relevant runtime components:

- [mcp_hub_path_scope_service.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/mcp-hub-tool-permissions/tldw_Server_API/app/services/mcp_hub_path_scope_service.py)
- [mcp_hub_path_enforcement_service.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/mcp-hub-tool-permissions/tldw_Server_API/app/services/mcp_hub_path_enforcement_service.py)
- [protocol.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/mcp-hub-tool-permissions/tldw_Server_API/app/core/MCP_unified/protocol.py)
- [mcp_hub_approval_service.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/mcp-hub-tool-permissions/tldw_Server_API/app/services/mcp_hub_approval_service.py)
- [persona.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/mcp-hub-tool-permissions/tldw_Server_API/app/api/v1/endpoints/persona.py)

Implementation shape:

1. resolve active workspace root/trust state
2. classify:
   - `workspace_unresolvable_for_trust_source`
   - `workspace_not_allowed_but_trusted`
3. feed the second case into runtime approval
4. preserve deny-only behavior for the first

## Scope Payload And Approval Key

Workspace approval scope payload should include:

- `workspace_id`
- `selected_assignment_id`
- `workspace_source_mode`
- `selected_workspace_trust_source`
- `allowed_workspace_ids`
- `reason`

The approval scope key should incorporate these fields along with `tool_name`.

This gives the desired reuse semantics:

- same tool + same workspace + same assignment -> reusable within duration
- different tool -> no reuse
- different assignment -> no reuse
- same workspace under a different trust source -> no reuse

## Persona And Runtime UX

### Approval Case

For a trusted but denied workspace, the runtime UI should show:

- tool name
- denied `workspace_id`
- trust source
- assignment context if available

Suggested message:

- `Approve tool access to trusted workspace 'docs' for this assignment?`

### Hard-Deny Case

For an unresolvable workspace, the runtime UI should show:

- no approval controls
- explicit trust-source failure messaging

Suggested message:

- `Blocked: workspace is not resolvable through the required trust source.`

## Testing Strategy

Backend:

- trusted resolvable workspace outside assignment membership -> approval required
- unresolvable workspace -> hard deny
- approval scope differs by tool name
- approval scope differs by assignment id
- approval scope differs by trust source
- approval does not mutate assignment membership

Persona/UI:

- approval card renders trusted denied `workspace_id`
- hard deny renders trust-source error text
- hard deny has no approval controls

Regression:

- existing path-scope approval still behaves the same
- untrusted workspace ids remain deny-only
- external slot approval behavior is unaffected

## Rollout

Implement in this order:

1. add failing runtime and UI tests
2. reorder workspace evaluation and classification
3. extend approval hashing and protocol approval routing
4. forward workspace governance payload through persona bridge
5. update persona UI messaging

This keeps the change narrow and preserves the trust boundary while making
workspace membership exceptions usable at runtime.
