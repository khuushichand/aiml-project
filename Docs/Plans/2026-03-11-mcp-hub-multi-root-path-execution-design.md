# MCP Hub Multi-Root Path Execution Design

Status: Implemented

## Goal

Allow one path-boundable MCP tool call to touch files under more than one trusted
workspace root without weakening MCP Hub trust or workspace-membership rules.

This first release is intentionally narrow:

- only `path_boundable` filesystem tools
- only `workspace_root` path-scope mode
- every matched workspace must already be trusted and already allowed
- approvals remain exact to the normalized path set across the exact workspace bundle

## Scope

This slice covers:

- multi-root path execution for `path_boundable` tools
- exact path-to-workspace mapping across a trusted workspace bundle
- deny-only handling for untrusted, unallowed, or ambiguous workspace matches
- exact approval scoping for path/allowlist misses inside an already-allowed bundle

This slice does not cover:

- multi-root `cwd_descendants`
- non-path-boundable tools
- approvals that add missing workspaces
- client-supplied multi-root bundle hints
- arbitrary bundle selection outside MCP Hub policy and trusted resolver data

## Current Gap

The branch now has:

- trusted user-local and shared-registry workspace resolution
- reusable workspace sets and path-scope objects
- exact path approval scoping for single-root path enforcement

What is still missing is true multi-root execution for one request.

Today the runtime is still explicitly single-root:

- one `workspace_id`
- one `workspace_root`
- one optional `cwd`
- one `scope_root`

That is visible in:

- [mcp_hub_path_scope_service.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/mcp-hub-tool-permissions/tldw_Server_API/app/services/mcp_hub_path_scope_service.py)
- [mcp_hub_path_enforcement_service.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/mcp-hub-tool-permissions/tldw_Server_API/app/services/mcp_hub_path_enforcement_service.py)
- [mcp_hub_approval_service.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/mcp-hub-tool-permissions/tldw_Server_API/app/services/mcp_hub_approval_service.py)

## Review Corrections

### 1. Multi-root should be a bundle-mapping layer above the current single-root resolver

The current path-scope service returns one resolved root and one optional cwd.
That contract should remain intact for existing flows.

This slice should add a new layer above it:

- resolve the active root exactly as today
- resolve the rest of the trusted, assignment-allowed workspace bundle separately
- map each normalized candidate path onto one workspace in that bundle

Do not mutate the current single-root resolver into a many-root API in v1.

### 2. Relative paths must stay anchored to the active workspace only

Current path normalization uses one `base_path`.

For v1:

- relative paths are resolved only against the active workspace root or active cwd
- only absolute paths may land in secondary roots

Without that rule, the same relative path could be interpreted against multiple
roots, which is not safe or explainable.

### 3. Multi-root must not reuse the current workspace-membership approval escape hatch

Single-root runtime now allows approval for `workspace_not_allowed_but_trusted`.
That must not carry into multi-root execution.

For v1:

- if any matched workspace is trusted but not allowed by the assignment, hard deny
- if any matched workspace is untrusted or unresolvable, hard deny
- no runtime approval may add a missing workspace to the bundle

Approval remains only for path/allowlist misses after the bundle is already fully
trusted and fully allowed.

### 4. Overlapping workspace roots need an explicit v1 rule

With current ancestry checks, overlapping roots like `/repo` and `/repo/docs`
would make some candidate paths match more than one workspace.

For v1:

- any path that matches more than one workspace root is deny-only
- overlapping workspace bundles are therefore supported only for disjoint path
  usage; ambiguous matches fail closed

This may later be tightened into save-time overlap rejection, but that is not
required for the first runtime slice.

### 5. Approval scope and governance payload must become bundle-aware

Current approval scoping only knows singular root fields.

For multi-root approval, the scope payload must include:

- exact normalized path set
- exact matched workspace id bundle
- exact matched workspace root bundle or equivalent stable bundle identity
- existing assignment and trust-source identity

That keeps approvals from being reused across a different workspace bundle.

## Runtime Model

This slice introduces a new runtime classification layer for filesystem tool calls.

### Allow

The request is multi-root-safe when all of the following are true:

- tool is `path_boundable`
- policy mode is `workspace_root`
- each candidate path normalizes cleanly
- each candidate path maps to exactly one trusted workspace root
- every matched workspace is already allowed by the assignment workspace source
- every candidate path stays within that workspace’s path scope and allowlist

### Approval Required

Approval is eligible only after the workspace bundle is already valid.

That means:

- all matched workspaces are trusted
- all matched workspaces are allowed
- no path mapping is ambiguous

Then, and only then, existing path-scope misses remain approvable:

- `path_outside_workspace_scope`
- `path_outside_allowlist_scope`

Approval unit:

- exact `tool_name`
- exact normalized path set
- exact matched workspace bundle
- existing assignment/trust-source context

### Deny

The request is deny-only when any of the following are true:

- tool is not path-boundable
- policy mode is `cwd_descendants`
- any candidate path cannot be normalized
- any candidate path matches no trusted workspace root
- any candidate path matches more than one trusted workspace root
- any matched workspace is not allowed by the assignment

## Architecture

Add a new bundle-mapping layer, for example:

- `McpHubMultiRootPathResolver`

Responsibilities:

1. collect the trusted, assignment-allowed workspace bundle
2. normalize candidate paths
3. map each normalized path to exactly one workspace root
4. return:
   - matched workspace ids
   - matched workspace roots
   - per-path workspace mapping
   - deny reason if mapping fails

The existing services keep their jobs:

- [mcp_hub_path_scope_service.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/mcp-hub-tool-permissions/tldw_Server_API/app/services/mcp_hub_path_scope_service.py)
  remains the single-root resolver for the active workspace
- [mcp_hub_workspace_root_resolver.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/mcp-hub-tool-permissions/tldw_Server_API/app/services/mcp_hub_workspace_root_resolver.py)
  remains the primitive for resolving one trusted `workspace_id`
- [mcp_hub_path_enforcement_service.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/mcp-hub-tool-permissions/tldw_Server_API/app/services/mcp_hub_path_enforcement_service.py)
  gains multi-root orchestration above those pieces

## Path-To-Workspace Mapping

The mapping algorithm for v1 should be:

1. resolve the active root as today
2. resolve all other allowed workspace ids in the assignment workspace source
3. normalize each candidate path
4. for each path:
   - if relative, resolve against the active base path only
   - if absolute, compare against every workspace root in the trusted bundle
5. assign the path only if exactly one root contains it

Each matched path is then enforced relative to its own workspace root:

- workspace containment check uses the matched root
- allowlist prefixes are evaluated relative to that matched root

## Policy Constraints

V1 multi-root support applies only when:

- `path_scope_mode == "workspace_root"`

It does not apply when:

- `path_scope_mode == "cwd_descendants"`

Reason:

- the current request/session model carries only one `cwd`
- there is no safe per-root cwd contract yet

## MCP Hub And UI

This slice does not require a major new MCP Hub editor.

The existing assignment workspace sources already provide the bundle:

- inline workspace membership
- named workspace set

Small UI additions are enough:

- effective preview can say `Multi-root execution supported` only when:
  - policy mode is `workspace_root`
  - more than one workspace is allowed by the current assignment source
- runtime/persona deny messages should distinguish:
  - unmatched workspace root
  - ambiguous workspace root match
  - workspace not allowed for bundle

## Approval And Governance Payload

The path governance payload for multi-root cases should include:

- `workspace_bundle_ids`
- `workspace_bundle_roots`
- `normalized_paths`
- optionally `path_workspace_map`
- existing:
  - `selected_assignment_id`
  - `selected_workspace_trust_source`
  - `workspace_source_mode`

Approval hashing should include the exact workspace bundle and exact normalized
path set.

## Testing

Backend tests should cover:

- exact two-root success path
- absolute path into a second allowed root
- deny when a path is outside all trusted roots
- deny when a path lands in an unallowed workspace
- deny when a path matches multiple roots
- deny when mode is `cwd_descendants`
- approval scope changes when workspace bundle changes
- approval scope changes when normalized path set changes

UI/runtime tests should cover:

- hard-deny messaging for multi-root ambiguity and unallowed-workspace cases
- continued exact-path approval behavior when only path/allowlist scope is the blocker

## Rollout

Recommended order:

1. add failing tests for multi-root mapping and scoping
2. implement bundle resolver and mapping logic
3. wire deny-only membership handling for multi-root mode
4. extend approval scoping/payload
5. add focused persona/runtime messaging

## Recommendation

Build this as a narrow runtime capability slice, not as a broad MCP Hub UI
feature. The current MCP Hub policy model is already sufficient; the missing work
is exact path-to-workspace mapping and exact bundle-aware approval scoping.
