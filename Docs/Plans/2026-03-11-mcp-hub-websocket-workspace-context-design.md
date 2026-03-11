# MCP Hub WebSocket Workspace Context Design

Status: Reviewed for planning

## Goal

Extend direct MCP WebSocket callers to participate in MCP Hub path-scoped enforcement using trusted connection-time `workspace_id` and `cwd` metadata, with reconnect mismatch rejection when a stable `mcp_session_id` is reused.

## Scope

This slice covers:

- connection-time WebSocket query params:
  - `mcp_session_id`
  - `workspace_id`
  - `cwd`
- explicit session-bound workspace context for reconnect-aware sessions
- rejection of reconnects that change `user_id`, `workspace_id`, or `cwd`
- propagation of trusted workspace context into `RequestContext.metadata`
- reuse of the existing MCP Hub path-scope resolver/enforcer
- focused WebSocket endpoint tests for handshake and mismatch behavior

This slice does not cover:

- raw absolute workspace roots from clients
- per-message workspace overrides
- `initialize.params` workspace mutation
- multi-root workspaces
- path allowlists

## Current Gap

HTTP ingress now carries trusted `workspace_id` and `cwd` into MCP metadata, but WebSocket ingress does not. The current WebSocket path only authenticates and builds a connection-local metadata dict. It also keys MCP session state to `connection_id`, which means there is no stable reconnectable session identity and no place to enforce workspace-context mismatch across reconnects.

## Design Summary

### Connection-Time API

The WebSocket endpoint will accept optional query params:

- `mcp_session_id`
- `workspace_id`
- `cwd`

Rules:

- `workspace_id` and `cwd` are trimmed strings only
- no raw root/path query params are accepted
- if `mcp_session_id` is absent, the connection remains connection-scoped as today
- if `mcp_session_id` is present, the server creates or reuses stable session state keyed by that value

### Stable Session Binding

`SessionData` will grow explicit fields:

- `workspace_id: Optional[str]`
- `cwd: Optional[str]`

Binding rules for `mcp_session_id` sessions:

- first connection may bind `user_id`, `workspace_id`, and `cwd`
- reconnect must match all bound values
- mismatch closes the socket with `1008`
- missing workspace context on reconnect when one was previously bound is also a mismatch

This comparison happens before the socket is accepted and before the connection is registered in `self.connections`.

### RequestContext Semantics

When `mcp_session_id` is present, protocol calls should use it as `RequestContext.session_id`. When absent, the existing `connection_id` fallback remains.

This keeps runtime approval and session-sensitive policy behavior stable across reconnects for clients that opt into `mcp_session_id`.

### Metadata Propagation

Trusted WebSocket workspace context is copied from connection/session state into every protocol request:

- `metadata["workspace_id"]`
- `metadata["cwd"]`

This shape matches HTTP ingress exactly, so the existing:

- `McpHubWorkspaceRootResolver`
- `McpHubPathScopeService`
- `McpHubPathEnforcementService`

can remain unchanged.

### Initialize Handling

`initialize.params` may continue to populate:

- `clientInfo`
- `safe_config`

but it must not set or change:

- `workspace_id`
- `cwd`

WebSocket workspace context is connection-time only.

## Error Handling

Mismatch rejection reasons should be explicit and auditable:

- `Workspace context mismatch`
- `Session is bound to a different user`

The close code should remain `1008` for policy/auth-style rejection.

## Testing Strategy

Add real WebSocket handshake coverage with `TestClient.websocket_connect(...)`:

- connect with `workspace_id` and `cwd`, verify those reach protocol metadata
- reconnect with same `mcp_session_id` and same context, verify success
- reconnect with same `mcp_session_id` and different `workspace_id`, verify `1008`
- reconnect with same `mcp_session_id` and different `cwd`, verify `1008`
- verify `initialize` cannot override bound workspace context

Keep focused protocol/path-scope coverage only where it validates reuse of existing enforcement, not handshake behavior.

## Recommendation

Implement this as the direct WebSocket counterpart to the trusted HTTP workspace-root slice. Once complete, MCP Hub path-scoped enforcement will behave consistently across:

- sandbox-backed persona/session traffic
- direct MCP HTTP callers
- direct MCP WebSocket callers
