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
- `chat_tool_fail_fast` (bool, default `false`; accepted values: `true`/`false`) — when `true`, stop processing remaining tool calls on first failure/timeout

Environment overrides:

- `CHAT_AUTO_EXECUTE_TOOLS`
- `CHAT_MAX_TOOL_CALLS`
- `CHAT_TOOL_TIMEOUT_MS`
- `CHAT_TOOL_ALLOW_CATALOG`
- `CHAT_TOOL_IDEMPOTENCY`
- `CHAT_TOOL_AUTO_CONTINUE_ONCE`
- `CHAT_TOOL_FAIL_FAST`

Allow-catalog semantics:

- `""` (empty / blank) => no tools allowed (default; tools are opt-in)
- `*` => unrestricted (all tools allowed)
- comma-separated exact names and/or wildcard suffix prefixes (e.g. `notes.search,media.*`)
- invalid entries are ignored; if all entries are invalid, no tools are allowed

### Non-Streaming Tool Execution: Error Handling & Data Structures

#### Persisted Tool Message Schema

Each executed tool call is persisted as a `role=tool` message in the
conversation history. The schema extends the OpenAI-compatible `role=tool`
format with diagnostic fields for observability and replay:

```jsonc
{
  "role": "tool",
  "tool_call_id": "call_abc123",       // provider-assigned tool call ID
  "name": "notes.search",              // tool name (MCP tool identifier)
  "content": "<JSON string>",          // serialized result envelope (see below)
  // -- diagnostic fields --
  "input": { "q": "hello" },           // arguments sent to the tool (echoed back)
  "status": "success",                 // "success" | "failure" | "timeout"
  "result": { ... },                   // tool output on success; null on failure/timeout
  "error": null,                       // null on success; structured object on failure/timeout:
                                       //   { "code": "TIMEOUT" | "CATALOG_DENIED" | "EXECUTION_ERROR",
                                       //     "message": "human-readable description",
                                       //     "stack": null }
                                       // `stack` is populated only when debug logging is
                                       // enabled; always null in production.
  "start_time": "2026-02-08T12:00:00.000Z",  // ISO-8601 execution start
  "end_time":   "2026-02-08T12:00:00.312Z"   // ISO-8601 execution end (or timeout instant)
}
```

The `content` field contains a JSON-serialized envelope consumed by LLM
follow-up turns (which read `content` as a string). Its shape mirrors the
`_make_result_content` helper in `tool_auto_exec.py`:

```jsonc
{
  "ok": true,             // boolean aggregate success flag
  "name": "notes.search",
  "result": { ... },      // tool output or null
  "module": "notes",      // originating MCP module or null
  "error": null,          // error string or null
  // optional flags (present only when true):
  "skipped": true,        // call was denied by allow-catalog or failed to parse
  "timed_out": true       // call exceeded chat_tool_timeout_ms
}
```

#### Extension Metadata in Completion Payload (`tldw_tool_results`)

The non-streaming completion response includes two extension fields as
top-level siblings of the standard `choices` array:

- `tldw_tool_results` — array of per-call result objects.
- `tldw_tool_execution_status` — single string summarizing the aggregate
  outcome.

```jsonc
{
  "choices": [ ... ],
  "usage": { ... },
  "tldw_conversation_id": "conv-123",
  "tldw_tool_results": [
    {
      "tool_call_id": "call_abc123",
      "status": "success",                  // "success" | "failure" | "timeout"
      "summary": "notes.search completed",  // human-readable one-liner
      "raw_result": { ... },                // full tool output (success) or null
      "error": null                         // null on success; structured error on failure:
                                            //   { "code": "...", "message": "..." }
    },
    {
      "tool_call_id": "call_def456",
      "status": "timeout",
      "summary": "media.ingest timed out after 15000ms",
      "raw_result": null,
      "error": {
        "code": "TIMEOUT",
        "message": "Tool execution timed out after 15000ms"
      }
    },
    {
      "tool_call_id": "call_ghi789",
      "status": "failure",
      "summary": "notes.delete failed: Permission denied",
      "raw_result": null,
      "error": {
        "code": "EXECUTION_ERROR",
        "message": "Permission denied"
      }
    }
  ],
  "tldw_tool_execution_status": "partial_success"
}
```

#### Execution Policy: Failure Handling

**Default: continue-on-error.** When `chat_auto_execute_tools=true`, the
executor iterates through up to `chat_max_tool_calls` calls sequentially. A
failure (execution error, catalog denial, or timeout) on any individual call
does **not** abort the remaining calls. All results — successes and failures
alike — are collected into the `tldw_tool_results` array and persisted as
`role=tool` messages.

Rationale: tool calls requested by an LLM are typically independent (e.g.
search notes + search media). Aborting the batch on the first failure would
discard useful results from subsequent successful calls.

**Configurable fail-fast option:**

```
[Chat-Module]
chat_tool_fail_fast = false   # default: false (continue-on-error)
```

Environment override: `CHAT_TOOL_FAIL_FAST`

`chat_tool_fail_fast` is a boolean flag and accepts only `true`/`false`
(`CHAT_TOOL_FAIL_FAST` uses the same boolean parsing). There is no numeric
clamping for this key; invalid/unset values resolve to the default `false`.

When `chat_tool_fail_fast=true`, the executor stops processing the batch
immediately upon the first non-success outcome (failure or timeout).
Results already collected up to and including the failed call are still
returned and persisted. The `ToolExecutionBatchResult.truncated` flag is
set to `true` to indicate early termination. This mode is appropriate when
tool calls have ordering dependencies (e.g. create-then-read) and a failed
prerequisite makes subsequent calls meaningless.

#### Timeout Handling

Each tool call is subject to the per-call deadline `chat_tool_timeout_ms`
(default `15000`, clamped to `1000..120000`). The timeout is enforced via
`asyncio.wait_for` around the MCP `tools/call` coroutine.

When a call times out:

1. The `asyncio.TimeoutError` is caught; the call is **not** retried.
2. A `ToolExecutionRecord` is created with:
   - `ok = false`
   - `timed_out = true`
   - `status = "timeout"`
   - `error = { "code": "TIMEOUT", "message": "Tool execution timed out after {timeout_ms}ms" }`
3. The record is persisted as a `role=tool` message so the conversation
   history accurately reflects the attempt (and the LLM can reason about
   the failure on a follow-up turn).
4. Under continue-on-error (default), the next tool call in the batch
   proceeds normally. Under fail-fast, the batch terminates immediately.

There is no aggregate batch-level timeout; each call receives the full
`chat_tool_timeout_ms` budget independently. A batch of `N` calls could
therefore take up to `N * chat_tool_timeout_ms` in the worst case.

#### Mixed Success/Failure Representation

When a batch contains a mix of successes and failures, **all** records are
included in `tldw_tool_results` in their original positional order (matching
the `tool_calls` array from the assistant message). The
`tldw_tool_execution_status` field summarizes the aggregate outcome:

| Condition | `tldw_tool_execution_status` |
|---|---|
| All calls succeeded | `"success"` |
| All calls failed or timed out | `"failure"` |
| At least one success + at least one failure/timeout | `"partial_success"` |
| No calls attempted (empty allow-catalog, no tool_calls, feature disabled) | `"skipped"` |

The `ToolExecutionBatchResult` dataclass exposes raw counts for programmatic
consumers:

- `requested_calls` — total tool calls in the assistant message
- `processed_calls` — calls selected after applying `chat_max_tool_calls` cap
- `execution_attempts` — calls that passed catalog/parse checks and were
  dispatched to MCP
- `executed_calls` — calls that completed successfully
- `truncated` — `true` when `requested_calls > processed_calls` (cap hit) or
  when fail-fast terminated the batch early

Clients can use `tldw_tool_execution_status` for coarse-grained UX decisions
(e.g. show a warning banner on `partial_success`) and inspect individual
`tldw_tool_results[].status` entries for fine-grained per-call handling.

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
