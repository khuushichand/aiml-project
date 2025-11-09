# Tools

## 1. Descriptive of Current Feature Set

- Purpose: Server-side wrapper to execute MCP Unified tools from within API handlers or services, decoupling call sites from MCP protocol details and centralizing permission/argument checks.
- Capabilities:
  - List available tools (respecting RBAC and catalog scoping) and check `canExecute`.
  - Execute tools with optional idempotency keys and validation-only mode.
  - Propagate request/user context to MCP via `RequestContext`.
- Inputs/Outputs:
  - Input: tool name, arguments dict, optional idempotency key, caller context (user_id, client_id).
  - Output: tool result payload or an error with reason.
- Related Endpoints (MCP Unified routes):
  - POST `/api/v1/mcp/request` (HTTP JSON-RPC proxy) — tldw_Server_API/app/api/v1/endpoints/mcp_unified_endpoint.py:252
  - WS `/api/v1/mcp/ws` — tldw_Server_API/app/api/v1/endpoints/mcp_unified_endpoint.py:206
  - Tool execution helper endpoint (HTTP wrapper) — `/api/v1/mcp/tools/execute`: tldw_Server_API/app/api/v1/endpoints/mcp_unified_endpoint.py:622
- Related Types
  - `MCPRequest`, `RequestContext`: tldw_Server_API/app/core/MCP_unified/protocol.py:58, 106

## 2. Technical Details of Features

- Architecture & Data Flow
  - `ToolExecutor` wraps MCP Unified’s server protocol to provide two entry points: `list_tools(...)` and `execute(...)`: tldw_Server_API/app/core/Tools/tool_executor.py:1
  - Validation-only flow calls `tools/list` and inspects `canExecute` for the requested tool.
  - Execution flow calls `tools/call` with `arguments` and optional `idempotencyKey`.
  - Context includes `user_id`, `client_id`, optional `request_id`, and `admin_override` metadata (for admin-only flows).

- Error Handling
  - Raises `ToolExecutionError` on MCP error responses or permission denials; callers map to appropriate HTTP responses.

- Security
  - Relies on MCP Unified auth + RBAC. Do not bypass `canExecute` checks; prefer `validate_only=True` to preflight from UI flows.

## 3. Developer-Related/Relevant Information for Contributors

- Folder Structure
  - `tool_executor.py` — thin MCP wrapper and error type.
- Extension Points
  - Add convenience wrappers per domain (e.g., `execute_media_search(...)`) in calling modules, keeping this module protocol-focused.
- Tests (selection)
  - MCP HTTP/JSON-RPC behavior for `tools/list`: tldw_Server_API/tests/e2e/test_mcp_basic.py:54–60
  - Permission mapping (403), `tools/list` shape: tldw_Server_API/tests/MCP/test_mcp_http_403_mapping.py:22
- Local Dev Tips
  - Ensure MCP Unified server is configured and running (or initialized in-process) before invoking `ToolExecutor`.
