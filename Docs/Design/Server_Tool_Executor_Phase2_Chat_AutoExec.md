# Server Tool Executor Phase 2: Chat Auto-Execution Addendum

## Intent
Integrate MCP-backed server tool execution into Chat flows in a gated, default-off way.

## Config Contract
`[Chat-Module]` keys:

- `chat_auto_execute_tools` (bool, default `false`)
- `chat_max_tool_calls` (int, default `3`, clamped to `1..20`)
- `chat_tool_timeout_ms` (int, default `15000`, clamped to `1000..120000`)
- `chat_tool_allow_catalog` (string, default `*`)
- `chat_tool_idempotency` (bool, default `true`)
- `chat_tool_auto_continue_once` (bool, default `false`)

Environment overrides:

- `CHAT_AUTO_EXECUTE_TOOLS`
- `CHAT_MAX_TOOL_CALLS`
- `CHAT_TOOL_TIMEOUT_MS`
- `CHAT_TOOL_ALLOW_CATALOG`
- `CHAT_TOOL_IDEMPOTENCY`
- `CHAT_TOOL_AUTO_CONTINUE_ONCE`

Allow-catalog semantics:

- `*` or blank => unrestricted
- comma-separated exact names and/or wildcard suffix prefixes (e.g. `notes.search,media.*`)
- invalid entries are ignored

## Non-Streaming Flow (target behavior)
1. Provider returns assistant `tool_calls` in the first completion.
2. If `chat_auto_execute_tools=false`, return existing response behavior unchanged.
3. If enabled:
   - Execute up to `chat_max_tool_calls`.
   - Enforce per-call timeout `chat_tool_timeout_ms`.
   - Enforce allow-catalog constraints.
   - Persist `role=tool` messages with `tool_call_id` metadata.
4. Return normal completion payload plus extension metadata for tool results.

## Streaming Flow (target behavior)
1. Stream assistant chunks and accumulate `tool_calls` as today.
2. On stream finalize, run tool execution (same policy controls as non-streaming).
3. Emit SSE event:
   - `event: tool_results`
   - `data: {"tool_results":[...]}`
4. Preserve existing stream framing (`stream_start`, `stream_end`, `[DONE]`).

## Optional Auto-Continue (Stage 5)
1. If `chat_tool_auto_continue_once=true` and non-streaming auto-exec produced at least one tool result:
   - Build a one-shot follow-up request with:
     - original request messages
     - first assistant tool-call message
     - generated `role=tool` messages
   - Execute a single follow-up assistant turn.
2. Persist follow-up assistant message when chat persistence is enabled.
3. Never recurse in the same request (at most one continuation turn).
4. Expose continuation status in response metadata:
   - `tldw_tool_auto_continue: { attempted: bool, succeeded: bool }`

## Safety Invariants
- Endpoint auth/RBAC remains unchanged.
- MCP remains authoritative for per-tool permission and write-policy enforcement.
- Tool auto-execution failures must be isolated to tool result records; they should not crash the chat endpoint.
- Auto-continue failures must not fail the request; the original assistant/tool outputs remain authoritative.
- Default behavior must remain unchanged when `chat_auto_execute_tools=false`.
