# Server Tool Executor (MCP-backed) - Design

This document outlines a safe, RBAC-controlled server-side tool executor integrated with the existing MCP Unified module. It adds a small, focused API surface and a reusable service so Chat can optionally auto-execute tools in future work.

## Goals

- Execute model-proposed function/tool calls on the server in a controlled way.
- Enforce per-tool permissions (RBAC) and server policies (disable write tools, input validation, idempotency).
- Provide a simple REST API for discovery and ad-hoc execution (UX and tests).
- Leave Chat behavior unchanged by default; enable server execution via config later.

## Non-Goals (phase 1)

- Changing default Chat to auto-execute tools.
- Adding new MCP modules.

## Architecture

- Reuse MCP Unified server (already production-grade): permission checks, input schema validation, write-tool policy, idempotency cache.
- New wrapper service: `app/core/Tools/tool_executor.py` encapsulates MCP requests:
  - `list_tools(user_id, client_id)` → calls `tools/list`, returns `canExecute` per tool.
  - `execute(user_id, client_id, tool_name, arguments, idempotency_key, validate_only)` → calls `tools/call` or performs a dry-run permission probe.

## API Surface (new)

- `GET /api/v1/tools` → List tools visible to the current user (MCP `canExecute` included). Auth required; no special permission.
- `POST /api/v1/tools/execute` → Execute a tool.
  - Body: `{ tool_name, arguments, idempotency_key?, dry_run? }`
  - RBAC gate: requires `tools.execute:*` (wildcard) at the endpoint layer, then per-tool check inside MCP. This provides a two-layer control plane.

Schemas live in `app/api/v1/schemas/tools.py`.

## ACLs & Controls

- RBAC (AuthNZ DB):
  - Endpoint requires `tools.execute:*` (via `PermissionChecker`).
  - MCP protocol enforces `tools.execute:{tool_name}` (or wildcard), `modules.read:{module}` when needed, and scoped permissions.
- Write-capable tools:
  - Disabled when `MCP_DISABLE_WRITE_TOOLS=1`.
  - Require `module.validate_tool_arguments` override; protocol validates `inputSchema` (config-gated) and calls validator.
  - Optional idempotency via `idempotencyKey` to dedupe retries.
- Rate limits: MCP has a per-category limiter; endpoint can add `Depends(rbac_rate_limit("tools.execute"))` later if needed.

## Configuration (phase 2: Chat integration)

Add to `config.txt` / ENV:

```
[Chat-Module]
chat_auto_execute_tools = false        # default off
chat_max_tool_calls = 3               # per response ceiling
chat_tool_timeout_ms = 15000          # per call budget
chat_tool_allow_catalog = *           # comma-sep names/prefixes or '*' (server still enforces RBAC)
chat_tool_idempotency = true          # attach idempotencyKey for write tools
```

Server will only auto-execute when explicitly enabled; otherwise behavior stays as today.

## Chat Integration (proposed flow)

1. Provider returns assistant `tool_calls` (OpenAI-style) in streaming or non-streaming path.
2. If `chat_auto_execute_tools` enabled:
   - For each tool_call (up to `chat_max_tool_calls`):
     - Call `ToolExecutor.execute` with user context.
     - On success, persist a `role=tool` message with `{name, content}` into the conversation.
     - Stream an event (NDJSON) `{ "tool_results": [{ name, content }] }` to the client.
   - Optionally auto-continue one more assistant turn using the updated history.
3. Full audit and usage logging already occurs inside MCP; add a lightweight “tool_executed” audit at Chat layer if needed.

## Security Considerations

- Never allow untrusted arguments to override `user_id`, DB paths, or server internals (MCP protocol sanitizes common keys).
- Disable write-capable tools by default in production unless explicitly enabled.
- Require explicit RBAC grants per tool (or wildcard) for non-admin users.
- Enforce per-request budgets and a global per-response cap (`chat_max_tool_calls`).

## Files Added

- `app/core/Tools/tool_executor.py` - MCP wrapper.
- `app/api/v1/schemas/tools.py` - Pydantic models.
- `app/api/v1/endpoints/tools.py` - List + Execute endpoints (gated by `route_enabled("tools")`).
- `app/main.py` - Router inclusion behind route gate (default disabled for stability).

## Future Work

- Add `rbac_rate_limit("tools.execute")` dependency to `/tools/execute`.
- Persist tool results as artifacts when configured.
- Wire into Chat (`chat_service` streaming and non-streaming paths) under config flag.
- Admin UI for granting `tools.execute:*` and per-tool permissions (backend already supports via Admin endpoints).
