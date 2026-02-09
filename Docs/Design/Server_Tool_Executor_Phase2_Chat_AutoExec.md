# Server Tool Executor Phase 2: Chat Auto-Execution Addendum

## Intent
Integrate MCP-backed server tool execution into Chat flows in a gated, default-off way.

## Config Contract
`[Chat-Module]` keys:

- `chat_auto_execute_tools` (bool, default `false`)
- `chat_max_tool_calls` (int, default `3`, clamped to `1..20`)
- `chat_tool_timeout_ms` (int, default `15000`, clamped to `1000..120000`)
- `chat_tool_allow_catalog` (string, default `""` — no tools allowed; explicit opt-in required)
- `chat_tool_idempotency` (bool, default `true`) — see [Idempotency Key Generation](#idempotency-key-generation) below
- `chat_tool_auto_continue_once` (bool, default `false`)

Environment overrides:

- `CHAT_AUTO_EXECUTE_TOOLS`
- `CHAT_MAX_TOOL_CALLS`
- `CHAT_TOOL_TIMEOUT_MS`
- `CHAT_TOOL_ALLOW_CATALOG`
- `CHAT_TOOL_IDEMPOTENCY`
- `CHAT_TOOL_AUTO_CONTINUE_ONCE`

Allow-catalog semantics:

- `""` (empty / blank) => no tools allowed (default; tools are opt-in)
- `*` => unrestricted (all tools allowed)
- comma-separated exact names and/or wildcard suffix prefixes (e.g. `notes.search,media.*`)
- invalid entries are ignored; if all entries are invalid, no tools are allowed

### Idempotency Key Generation

**Parameter**: `chat_tool_idempotency` (bool, default `true`)

**Definition**: Controls whether the chat auto-execution pipeline generates and
attaches an `idempotencyKey` to each MCP `tools/call` JSON-RPC request. The key
enables the MCP protocol layer to deduplicate write-tool calls — if the same key
and arguments arrive again (e.g. due to a client retry or auto-continue
replaying the same tool call), the MCP server returns the cached result from the
first execution instead of running the tool a second time.

**Key construction** (`build_tool_idempotency_key` in `tool_auto_exec.py`):

```
chat:{seed}:{tool_call_id}:{tool_name}:{args_sha256_prefix}
```

- `seed` — derived from `conversation_id` when available, otherwise
  `{user_id}:{client_id}`. Sanitized to alphanumeric/underscore/hyphen.
- `tool_call_id` — the provider-assigned call ID from the assistant message.
- `tool_name` — the MCP tool name being invoked.
- `args_sha256_prefix` — first 16 hex characters of the SHA-256 digest of the
  canonicalized (sorted-keys) JSON arguments.
- The final key is truncated to 200 characters.

**MCP-side behavior**: The MCP protocol (`protocol.py`) checks the
`idempotencyKey` only for **write** tools (tools whose module marks them as
mutating). For write calls, MCP binds the key to the argument hash, acquires an
execution lock, and caches the result with a configurable TTL (default 300 s).
A subsequent call with the same key and arguments returns the cached result
(idempotency hit). A call with the same key but different arguments is rejected
with an `INVALID_PARAMS` error. Read-only tools ignore the key entirely and
always execute.

**When `true` (default)**:

- Each auto-executed tool call includes an `idempotencyKey` in its MCP request
  params.
- Write-tool calls are safe against duplicate execution from retries, network
  replays, or auto-continue re-sending the same tool call.

**When `false`**:

- No `idempotencyKey` is attached. Tool calls are passed to MCP without
  deduplication.
- Each invocation executes unconditionally, even if it is a repeat of an
  identical earlier call.
- Appropriate when all tools in the allow-catalog are read-only, or when the
  caller explicitly wants every invocation to execute (e.g. tools with
  intentional side effects on each call).

**Example**:

```
# With chat_tool_idempotency = true
# Assistant requests: notes.create({"title": "Meeting notes", "body": "..."})
# Auto-exec sends to MCP:
#   tools/call { name: "notes.create",
#                arguments: { title: "Meeting notes", body: "..." },
#                idempotencyKey: "chat:conv_42:call_0:notes.create:a1b2c3d4e5f67890" }
#
# If auto-continue replays the same tool call, MCP returns the cached
# result from the first execution — the note is created only once.

# With chat_tool_idempotency = false
# Auto-exec sends to MCP:
#   tools/call { name: "notes.create",
#                arguments: { title: "Meeting notes", body: "..." },
#                idempotencyKey: null }
#
# Every invocation creates a new note, even if arguments are identical.
```

## Non-Streaming Flow (target behavior)
1. Provider returns assistant `tool_calls` in the first completion.
2. If `chat_auto_execute_tools=false`, return existing response behavior unchanged.
3. If enabled:
   - Execute up to `chat_max_tool_calls`.
   - Enforce per-call timeout `chat_tool_timeout_ms`.
   - Enforce allow-catalog constraints.
   - If `chat_tool_idempotency=true`, generate an idempotency key per call and
     pass it as `idempotencyKey` in the MCP request. The seed is derived from
     the conversation ID when persistence is enabled.
   - Persist `role=tool` messages with `tool_call_id` metadata.
4. Return normal completion payload plus extension metadata for tool results.

## Streaming Flow (target behavior)
1. Stream assistant chunks and accumulate `tool_calls` as today.
2. On `stream_end`, begin tool execution (same policy controls as non-streaming).
   Tool execution is **post-stream**: all assistant content chunks have already been
   delivered to the client before execution starts, so tool work never blocks or
   delays the streamed assistant response. Execution runs sequentially through up
   to `chat_max_tool_calls` calls, each subject to the per-call
   `chat_tool_timeout_ms` deadline. If any individual call exceeds
   `chat_tool_timeout_ms`, that call is aborted and its entry in the results array
   carries `"status": "timeout"` with an `"error"` field describing the timeout
   (e.g. `"error": "Tool execution exceeded 15000 ms"`). Remaining calls in the
   batch still execute; a single timeout does not cancel the whole batch.
   If `chat_tool_idempotency=true`, idempotency keys are generated identically
   to the non-streaming path, using the conversation ID as the seed.
3. After all calls complete (or timeout), emit a single SSE frame:
   - `event: tool_results`
   - `data: {"tool_results":[{"tool_call_id":"...","status":"ok|timeout|error","output":...,"error":...}, ...]}`
   This event is sent **after** `stream_end` and **before** the final `[DONE]`
   sentinel, giving clients a deterministic ordering:
   `stream_start → content chunks → stream_end → tool_results → [DONE]`.
4. Emit `[DONE]` to close the stream. The existing `stream_start` / `stream_end`
   framing is unchanged; `tool_results` is an additive event between `stream_end`
   and `[DONE]`.

## Optional Auto-Continue (Stage 5)

Auto-continue only applies to non-streaming flows (i.e. when
`chat_tool_auto_continue_once=true` is used with non-streaming auto-exec).

1. If `chat_tool_auto_continue_once=true` and non-streaming auto-exec produced at least one tool result:
   - Build a one-shot follow-up request with:
     - original request messages
     - first assistant tool-call message
     - generated `role=tool` messages
   - Execute a single follow-up assistant turn.
   - If the follow-up assistant turn itself returns `tool_calls`, those calls
     are **not** auto-executed. They are persisted (when persistence is enabled)
     and returned to the client in the response payload as-is, giving the client
     the option to handle them. This is the no-recursion guarantee: at most one
     continuation turn is performed per request.
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
- Idempotency keys are scoped per user/conversation and per tool-call ID, preventing cross-user or cross-conversation cache collisions.
