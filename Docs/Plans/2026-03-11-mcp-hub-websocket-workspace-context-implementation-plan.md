# MCP Hub WebSocket Workspace Context Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add trusted connection-time WebSocket workspace context with stable reconnect-aware `mcp_session_id` binding so direct MCP WebSocket callers participate in MCP Hub path-scoped enforcement.

**Architecture:** Extend MCP WebSocket ingress with optional `mcp_session_id`, `workspace_id`, and `cwd` query params, bind those onto explicit session state before socket accept, and feed the existing MCP Hub path-scope pipeline through unchanged request metadata. Reconnect mismatch checks are enforced only for clients that opt into stable `mcp_session_id`.

**Tech Stack:** FastAPI WebSocket endpoint, MCP unified server/session layer, MCP protocol, pytest, Bandit

---

## Status

- Task 1: Not started
- Task 2: Not started
- Task 3: Not started
- Task 4: Not started
- Task 5: Not started
- Task 6: Not started

### Task 1: Add failing WebSocket ingress and mismatch tests

**Files:**
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_http_auth_paths.py` or add a new focused WebSocket MCP endpoint suite if cleaner
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_sessions.py` if session semantics fit there

**Step 1: Add failing handshake tests**

Add tests that expect:

- WebSocket connect with `workspace_id` and `cwd` makes them visible to request metadata
- reconnect with the same `mcp_session_id` and the same context succeeds
- reconnect with the same `mcp_session_id` and a different `workspace_id` fails with close `1008`
- reconnect with the same `mcp_session_id` and a different `cwd` fails with close `1008`

**Step 2: Add failing initialize-mutation test**

Add a test that sends `initialize` carrying workspace-like fields and verifies they do not override connection-bound context.

**Step 3: Run focused tests and confirm failure**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_http_auth_paths.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_sessions.py -k "websocket or workspace or session" -v
```

Expected: FAIL.

### Task 2: Add explicit workspace context to MCP WebSocket session state

**Files:**
- Modify: `tldw_Server_API/app/core/MCP_unified/server.py`

**Step 1: Extend session state**

Add explicit `SessionData` fields:

- `workspace_id`
- `cwd`

Do not store them only in loose metadata.

**Step 2: Add stable session binding helper**

Implement a helper that:

- creates or reuses session state by `mcp_session_id`
- binds `user_id`, `workspace_id`, and `cwd` on first use
- rejects mismatches on reconnect

**Step 3: Keep current fallback behavior**

If `mcp_session_id` is absent, preserve existing connection-scoped session behavior.

**Step 4: Run focused session tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_sessions.py -k "workspace or session" -v
```

Expected: PASS.

### Task 3: Add WebSocket query-param ingress for workspace context

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/mcp_unified_endpoint.py`
- Modify: `tldw_Server_API/app/core/MCP_unified/server.py`

**Step 1: Extend `/mcp/ws` query params**

Add optional:

- `mcp_session_id`
- `workspace_id`
- `cwd`

Pass them into `handle_websocket(...)`.

**Step 2: Validate before accept**

In `handle_websocket(...)`:

- normalize trimmed string values
- bind/check workspace context before `stream.start()` and before connection registration
- reject mismatch with `1008`

**Step 3: Run focused WebSocket ingress tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_http_auth_paths.py -k "websocket and workspace" -v
```

Expected: PASS.

### Task 4: Propagate stable workspace context into RequestContext

**Files:**
- Modify: `tldw_Server_API/app/core/MCP_unified/server.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py` if protocol coverage needs one direct WS-style case

**Step 1: Build request metadata from bound session/connection context**

Ensure each WebSocket request gets:

- `workspace_id`
- `cwd`

from the bound context, not from request payloads.

**Step 2: Use stable `mcp_session_id` when present**

Set `RequestContext.session_id` to the stable session id when one exists; otherwise keep `connection_id`.

**Step 3: Run focused path-scope tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py -k "workspace" -v
```

Expected: PASS.

### Task 5: Forbid initialize-time workspace mutation

**Files:**
- Modify: `tldw_Server_API/app/core/MCP_unified/server.py`
- Modify: relevant WebSocket endpoint tests

**Step 1: Preserve allowed initialize fields only**

Keep `clientInfo` and `safe_config` handling.

Do not read or apply:

- `workspace_id`
- `cwd`

from `initialize.params`.

**Step 2: Run focused tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_http_auth_paths.py -k "initialize or websocket" -v
```

Expected: PASS.

### Task 6: Full verification and Bandit

**Files:**
- No new files expected

**Step 1: Run focused verification**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_http_auth_paths.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_sessions.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_protocol_path_scope.py -v

source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/api/v1/endpoints/mcp_unified_endpoint.py \
  tldw_Server_API/app/core/MCP_unified/server.py \
  -f json -o /tmp/bandit_mcp_hub_websocket_workspace_context.json
```

Expected:

- focused pytest suites PASS
- Bandit reports no new findings in touched code

---

## Definition Of Done

- Direct MCP WebSocket callers can provide trusted `workspace_id` and `cwd` at connection time
- Stable `mcp_session_id` reconnects reject workspace-context mismatch
- WebSocket request metadata matches the HTTP metadata shape used by MCP Hub path scope
- `initialize` cannot mutate workspace context
- Existing WebSocket clients without `mcp_session_id` continue to work
