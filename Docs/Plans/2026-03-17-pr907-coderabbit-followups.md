# PR 907 CodeRabbit Followups Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Address the verified new PR #907 review findings around ACP/MCP adapter robustness, transport cleanup, runner validation, registry MCP-field persistence, and remaining test hygiene.

**Architecture:** Tighten failure handling at adapter and transport boundaries so partial MCP connections cannot leak live clients or stale state, fail fast on invalid protocol/orchestration configuration, and make structured/LLM runner paths validate malformed inputs instead of crashing. Extend the agent registry and ACP session persistence path so MCP orchestration fields survive YAML/API/DB round-trips, then lock the behavior in with targeted unit tests before touching production code.

**Tech Stack:** Python 3.11+, FastAPI/Pydantic, asyncio, SQLite, pytest, loguru, Bandit, pre-commit.

---

### Task 1: Add failing adapter and runner regression tests
**Status:** Complete

**Files:**
- Modify: `tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_adapter.py`
- Modify: `tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_runners_llm.py`
- Modify: `tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_runners_agent.py`

**Step 1: Write the failing tests**

- Add adapter tests for:
  - `connect()` cleaning up transport/config/tools/connected state when lifecycle emit or `list_tools()` fails.
  - `send_prompt()` rejecting an unknown `mcp_orchestration` value.
- Add runner tests for:
  - structured responses with missing required fields emitting `ERROR` instead of `KeyError`.
  - LLM multi-tool responses stopping before approving/executing later tools once cancellation is set during the tool loop.

**Step 2: Run the targeted tests to verify they fail**

Run:
```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_adapter.py tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_runners_agent.py tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_runners_llm.py -q
```

**Step 3: Write the minimal production changes**

- Update `mcp_adapter.py` to:
  - clean up transport/config/tools on failed connect.
  - reject unknown orchestration modes with a deterministic config validation error.
- Update `mcp_runners.py` to:
  - validate structured step payloads per step type and emit `ERROR` for malformed steps.
  - re-check cancellation inside the per-tool loop.
  - convert the `%r` Loguru warning format to `{!r}`.

**Step 4: Re-run the targeted tests**

Run the same pytest command and confirm green.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_adapter.py tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_runners.py tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_adapter.py tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_runners_agent.py tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_runners_llm.py
git commit -m "fix(acp): harden adapter and runner review followups"
```

### Task 2: Add failing transport factory and transport cleanup tests
**Status:** Complete

**Files:**
- Modify: `tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_transport.py`
- Modify: `tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_stdio_transport.py`
- Modify: `tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_sse_transport.py`
- Modify: `tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_streamable_http_transport.py`

**Step 1: Write the failing tests**

- Add transport-factory tests for missing required keys (`command`, `sse_url`, `endpoint`).
- Add stdio tests for handshake failure cleanup, `close()` clearing `_client`, and list/call methods refusing disconnected clients.
- Add SSE tests for:
  - handshake failure cleanup.
  - parser support for multi-line `data:` frames and default `"message"` event type.
  - pending RPC futures being failed on reader-loop shutdown.
- Add streamable HTTP tests for handshake failure cleanup.

**Step 2: Run the targeted tests to verify they fail**

Run:
```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_transport.py tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_stdio_transport.py tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_sse_transport.py tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_streamable_http_transport.py -q
```

**Step 3: Write the minimal production changes**

- Update `mcp_transport.py` to validate required config keys with a project exception.
- Update `stdio.py`, `sse.py`, and `streamable_http.py` to clean up failed handshakes and stale clients.
- Add a shared SSE teardown path for disconnect/error handling and improve the SSE parser for multiline/default-event frames.

**Step 4: Re-run the targeted tests**

Run the same pytest command and confirm green.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_transport.py tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_transports/stdio.py tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_transports/sse.py tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_transports/streamable_http.py tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_transport.py tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_stdio_transport.py tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_sse_transport.py tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_streamable_http_transport.py
git commit -m "fix(acp): harden MCP transport lifecycle handling"
```

### Task 3: Add failing registry persistence and API-shape tests
**Status:** Complete

**Files:**
- Modify: `tldw_Server_API/tests/Agent_Client_Protocol/test_acp_agent_registry.py`
- Modify: `tldw_Server_API/tests/Agent_Client_Protocol/test_acp_integration_persistence.py`
- Modify: `tldw_Server_API/tests/Agent_Client_Protocol/test_registry_mcp_fields.py`
- Modify: `tldw_Server_API/app/core/Agent_Client_Protocol/agent_registry.py`
- Modify: `tldw_Server_API/app/core/DB_Management/ACP_Sessions_DB.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/agent_client_protocol.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/agent_client_protocol.py`

**Step 1: Write the failing tests**

- Add YAML-loading tests proving MCP fields are populated into `AgentRegistryEntry`.
- Add dynamic-registration / reload tests proving MCP fields survive DB persistence and `update_agent()`.
- Add request-model tests, if needed, to prove API register/update payloads accept the MCP field set.

**Step 2: Run the targeted tests to verify they fail**

Run:
```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_acp_agent_registry.py tldw_Server_API/tests/Agent_Client_Protocol/test_acp_integration_persistence.py tldw_Server_API/tests/Agent_Client_Protocol/test_registry_mcp_fields.py -q
```

**Step 3: Write the minimal production changes**

- Extend `AgentRegistry.load()`, `_load_api_entries()`, `register_agent()`, `update_agent()`, and DB save/load paths to include the MCP field set.
- Add the necessary `agent_registry` schema columns/migrations in `ACP_Sessions_DB.py`.
- Extend ACP register/update request schemas and endpoint wiring to accept and pass through the MCP fields.

**Step 4: Re-run the targeted tests**

Run the same pytest command and confirm green.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Agent_Client_Protocol/agent_registry.py tldw_Server_API/app/core/DB_Management/ACP_Sessions_DB.py tldw_Server_API/app/api/v1/schemas/agent_client_protocol.py tldw_Server_API/app/api/v1/endpoints/agent_client_protocol.py tldw_Server_API/tests/Agent_Client_Protocol/test_acp_agent_registry.py tldw_Server_API/tests/Agent_Client_Protocol/test_acp_integration_persistence.py tldw_Server_API/tests/Agent_Client_Protocol/test_registry_mcp_fields.py
git commit -m "fix(acp): persist MCP registry configuration"
```

### Task 4: Clean up remaining test-only review comments and verify
**Status:** Complete

**Files:**
- Modify: `tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_adapter.py`
- Modify: `tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_runners_llm.py`
- Modify: `tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_streamable_http_transport.py`
- Modify: `tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_transport.py`
- Modify: `tldw_Server_API/tests/Agent_Client_Protocol/test_tool_gate.py`

**Step 1: Write/adjust tests**

- Remove unused fixture arguments in `test_mcp_adapter.py`.
- Use raw regex strings where regex metacharacters are intended.
- Rename intentionally unused unpacked helper returns with underscore-prefixed names.
- Rename helper parameters shadowing builtins in streamable HTTP tests.
- Replace the `"/tmp"` literal in `test_tool_gate.py` with a neutral placeholder.

**Step 2: Run the targeted tests and local hygiene gates**

Run:
```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_adapter.py tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_runners_llm.py tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_streamable_http_transport.py tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_transport.py tldw_Server_API/tests/Agent_Client_Protocol/test_tool_gate.py -q
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && pre-commit run --files tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_adapter.py tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_runners.py tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_transport.py tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_transports/stdio.py tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_transports/sse.py tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_transports/streamable_http.py tldw_Server_API/app/core/Agent_Client_Protocol/agent_registry.py tldw_Server_API/app/core/DB_Management/ACP_Sessions_DB.py tldw_Server_API/app/api/v1/schemas/agent_client_protocol.py tldw_Server_API/app/api/v1/endpoints/agent_client_protocol.py tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_adapter.py tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_runners_agent.py tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_runners_llm.py tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_transport.py tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_stdio_transport.py tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_sse_transport.py tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_streamable_http_transport.py tldw_Server_API/tests/Agent_Client_Protocol/test_acp_agent_registry.py tldw_Server_API/tests/Agent_Client_Protocol/test_acp_integration_persistence.py tldw_Server_API/tests/Agent_Client_Protocol/test_registry_mcp_fields.py tldw_Server_API/tests/Agent_Client_Protocol/test_tool_gate.py
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_adapter.py tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_runners.py tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_transport.py tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_transports/stdio.py tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_transports/sse.py tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_transports/streamable_http.py tldw_Server_API/app/core/Agent_Client_Protocol/agent_registry.py tldw_Server_API/app/core/DB_Management/ACP_Sessions_DB.py tldw_Server_API/app/api/v1/schemas/agent_client_protocol.py tldw_Server_API/app/api/v1/endpoints/agent_client_protocol.py -f json -o /tmp/bandit_pr907_coderabbit_followups.json
```

**Step 3: Commit**

```bash
git add tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_adapter.py tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_runners_llm.py tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_streamable_http_transport.py tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_transport.py tldw_Server_API/tests/Agent_Client_Protocol/test_tool_gate.py
git commit -m "test(acp): clean up remaining PR 907 review warnings"
```
