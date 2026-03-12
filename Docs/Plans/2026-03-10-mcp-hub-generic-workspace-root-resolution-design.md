# MCP Hub Generic Workspace Root Resolution Design

Status: Implemented

## Goal

Extend MCP Hub path-scoped enforcement beyond sandbox-session-only flows so direct MCP/API callers can participate in trusted `workspace_root` and `cwd_descendants` policy enforcement.

## Current State

Path scope currently trusts only sandbox session lookup in [mcp_hub_path_scope_service.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/mcp-hub-tool-permissions/tldw_Server_API/app/services/mcp_hub_path_scope_service.py). That works for persona/ACP flows that already have a sandbox session id, but it leaves direct MCP/API callers outside the enforceable workspace-root model.

There is no generic durable workspace registry today. The closest trusted source is sandbox state:

- `sandbox_sessions` stores `workspace_id` and `workspace_path`
- `sandbox_acp_sessions` stores ACP/session control metadata including `workspace_id`
- `SandboxOrchestrator.get_session_workspace_path(...)` resolves only by `session_id`

So the next slice should not invent a new global workspace model. It should add a narrow trusted resolver over existing sandbox-owned state and explicit direct-request metadata ingress.

## Review Corrections

### 1. Do not invent a second workspace source of truth

There is no existing global `workspace_id -> path` registry. The first version should resolve from trusted sandbox state only.

That means:

- prefer exact sandbox session resolution when `session_id` is present
- otherwise resolve by caller-owned active sandbox records keyed by `workspace_id`
- fail closed when no trusted match exists

Out of scope for this PR:

- a new durable global workspace registry
- arbitrary client-defined absolute roots

### 2. `workspace_id` must be scoped to the acting principal

`workspace_id` alone is not sufficient. A direct MCP caller must not be able to name another user’s workspace and inherit its path boundary.

The resolver must scope lookup by at least:

- `user_id`
- `workspace_id`

If multiple active records match and resolve to different `workspace_path` values, the resolver should return `workspace_root_ambiguous` and fail closed.

### 3. Direct MCP/API ingress needs an explicit trusted contract

The current MCP HTTP surfaces pass auth metadata and session id, but they do not currently expose a dedicated direct-caller `workspace_id` and `cwd` ingress contract.

The first version should add explicit request headers:

- `x-tldw-workspace-id`
- `x-tldw-cwd`

Reasons:

- avoids mutating JSON-RPC request bodies
- works for both `/mcp/request` and `/mcp/tools/execute`
- keeps the trust boundary in server-owned request metadata, not tool arguments

### 4. Resolver output needs stronger failure modes

Current path scope returns only `workspace_root_unavailable` or `cwd_outside_workspace_scope`.

The generic resolver should add:

- `workspace_root_unavailable`
- `workspace_root_ambiguous`
- `workspace_root_untrusted`
- `cwd_outside_workspace_scope`

These need to remain fail-closed and feed the existing approval/deny behavior cleanly.

## Proposed Architecture

Add a small `WorkspaceRootResolver` service that plugs into `McpHubPathScopeService`.

Inputs:

- `session_id`
- `user_id`
- request metadata
  - `workspace_id`
  - `cwd`

Resolution order:

1. If a sandbox session id is present and resolves to a workspace path, use it.
2. Otherwise, if `workspace_id` is present, resolve against trusted sandbox store records for the acting user.
3. If the lookup is missing, ambiguous, or untrusted, fail closed.

Resolver output:

- `workspace_root`
- `cwd`
- `workspace_id`
- `source`
  - `sandbox_session`
  - `sandbox_workspace_lookup`
- `reason`

## Trust Model

Trusted:

- sandbox session rows and control rows written by the sandbox/orchestrator layer
- authenticated `user_id`
- server-side canonicalization of `workspace_path`

Not trusted:

- arbitrary absolute path headers
- tool arguments containing local paths that attempt to redefine workspace scope
- `workspace_id` without principal scoping

## Lookup Semantics

For direct callers using `workspace_id`:

1. Load candidate sandbox-backed records for `(user_id, workspace_id)`.
2. Ignore expired or obviously invalid entries.
3. Canonicalize candidate `workspace_path` values.
4. If no valid paths remain, return `workspace_root_unavailable`.
5. If more than one distinct canonical path remains, return `workspace_root_ambiguous`.
6. Otherwise, use the single canonical path as `workspace_root`.

This keeps the first version deterministic and safe without building a new registry subsystem.

## Request Metadata Contract

Add optional trusted headers on direct MCP/API ingress:

- `x-tldw-workspace-id`
- `x-tldw-cwd`

The server copies these into request metadata only after authentication. Path enforcement then reads them from `RequestContext.metadata`, not from tool arguments.

Rules:

- `x-tldw-workspace-id` is an identifier only, never a path
- `x-tldw-cwd` is resolved relative to `workspace_root` unless absolute
- `cwd` must remain within `workspace_root`

## Enforcement Semantics

No new MCP Hub policy fields are needed. Reuse:

- `path_scope_mode`
  - `workspace_root`
  - `cwd_descendants`
- `path_scope_enforcement`

What changes is only how `workspace_root` is discovered for direct callers.

If no trusted root can be resolved, path-scoped policies still fail closed.

## API Surfaces

This PR should update:

- MCP HTTP JSON-RPC endpoint metadata ingestion
- `/mcp/tools/execute` wrapper metadata ingestion
- path-scope resolver service integration

No new end-user MCP Hub editor surface is required.

## Testing

Add tests for:

- direct MCP caller with trusted `workspace_id` header resolves path scope
- unknown `workspace_id` fails closed
- ambiguous `workspace_id` mapping fails closed
- `cwd` outside resolved root fails closed
- existing sandbox-session resolution still works
- direct `/mcp/tools/execute` carries headers into metadata and path scope

## Out Of Scope

- durable workspace registry outside sandbox state
- multi-root workspace support
- arbitrary user-entered path allowlists
- client-provided absolute workspace roots
- non-sandbox workspace providers

## Recommendation

Implement a narrow trusted resolver over existing sandbox session/control state, with explicit header-based direct MCP ingress. Do not try to solve a full cross-system workspace registry in this PR.
