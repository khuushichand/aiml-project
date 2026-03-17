# ACP MCP Adapter — Phase B Design Document

**Date**: 2026-03-16
**Status**: Approved
**Scope**: MCPAdapter for the ACP Agent Workspace Harness — multi-transport MCP client with configurable orchestration
**Depends on**: Phase A (merged) — AgentEvent, ProtocolAdapter, SessionEventBus, GovernanceFilter, consumers

---

## 1. Overview

Add an MCPAdapter that connects to agents exposing an MCP server interface. The adapter acts as an MCP client, discovers the agent's tools, and orchestrates tool execution either via an LLM-driven ReAct loop or by delegating to the agent's own orchestration. Supports three MCP transports: stdio, SSE, and streamable HTTP.

### Key Decisions

| Decision | Choice |
|----------|--------|
| Interaction model | Agent-as-tool-provider first, sampling support later |
| Orchestration | Configurable per-agent: `agent_driven` or `llm_driven` |
| Transports | All three: stdio, SSE, streamable HTTP |
| Transport code | Import `ExternalMCPTransportAdapter` ABC as reference, implement fresh |
| Governance integration | `ToolGate` protocol for llm_driven approval flow |
| Response format | Simple text (default), structured steps (opt-in) for agent_driven |

---

## 2. Architecture

```
User prompt
    │
    ▼
MCPAdapter.send_prompt(messages)
    │
    ├─ mcp_orchestration == "agent_driven"
    │     │
    │     ▼
    │   AgentDrivenRunner
    │     → call_tool(entry_tool, {messages}) via transport
    │     → simple: emit COMPLETION with text result
    │     → structured (opt-in): parse steps array, emit events
    │
    └─ mcp_orchestration == "llm_driven"
          │
          ▼
        LLMDrivenRunner
          → list_tools() → get tool definitions
          → send messages + tool_defs to LLM
          → LLM returns tool_call
              → ToolGate.request_approval() (governance)
              → if approved: call_tool() via transport
              → feed result back to LLM
          → repeat until LLM returns text → emit COMPLETION
```

### Components

- **`MCPAdapter`** — implements `ProtocolAdapter`, manages transport lifecycle, orchestration mode, cancellation
- **`MCPTransport`** (ABC) — connect/close/list_tools/call_tool/health_check/is_connected
- **`MCPStdioTransport`** — JSON-RPC 2.0 over stdin/stdout
- **`MCPSSETransport`** — SSE stream + HTTP POST
- **`MCPStreamableHTTPTransport`** — single HTTP endpoint with streaming/non-streaming responses
- **`AgentDrivenRunner`** — calls entry tool, translates response to events
- **`LLMDrivenRunner`** — ReAct loop with LLM, uses ToolGate for governance
- **`ToolGate`** (ABC) — approval interface between adapter and GovernanceFilter
- **`create_transport()`** — factory function dispatching by transport type

---

## 3. ToolGate Protocol

Solves the return-channel problem: the adapter needs to know whether GovernanceFilter approved a tool call before executing it.

```python
@dataclass
class ToolGateResult:
    approved: bool
    reason: str | None = None

class ToolGate(ABC):
    async def request_approval(
        self, session_id: str, tool_name: str, arguments: dict
    ) -> ToolGateResult:
        """Blocks until governance decision. Returns approved/denied."""
```

**Wiring:** The session coordinator creates a `ToolGate` implementation that:
1. Publishes a `tool_call` event via GovernanceFilter
2. If auto-approved → returns `ToolGateResult(approved=True)` immediately
3. If held → waits on `asyncio.Future` resolved by GovernanceFilter's `on_permission_response()`
4. Returns the decision

The MCPAdapter receives `ToolGate` via `protocol_config["tool_gate"]`.

- **llm_driven mode:** `LLMDrivenRunner` calls `await tool_gate.request_approval(...)` before every `transport.call_tool()`
- **agent_driven mode:** `ToolGate` unused — events are informational (agent already executed)

**Implementation location:** `ToolGate` ABC lives in `tool_gate.py` (clean, no dependencies). The concrete `GovernanceToolGate` implementation lives in `governance_filter.py` alongside `GovernanceFilter` — it knows how to interact with the filter's pending map and futures. MCPAdapter only imports the ABC, avoiding circular dependencies.

---

## 4. Transport Layer

### MCPTransport ABC

```python
class MCPTransport(ABC):
    async def connect(self) -> None
    async def close(self) -> None
    async def list_tools(self) -> list[dict[str, Any]]
    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]
    async def health_check(self) -> bool
    is_connected: bool  # property
```

### MCPStdioTransport

- **Composes `ACPStdioClient` internally** for JSON-RPC 2.0 framing, request/response matching, and process lifecycle — avoids reimplementing the wire protocol
- Adds MCP-specific methods on top: `initialize` handshake, `tools/list`, `tools/call`
- Handshake: `client.call("initialize", {...})` → `client.notify("initialized", {})` → `client.call("tools/list", {})`
- Protocol version: `"2024-11-05"`
- `is_connected` delegates to `client.is_running`

```python
class MCPStdioTransport(MCPTransport):
    def __init__(self, command, args, env):
        self._client = ACPStdioClient(command, args, env)

    async def connect(self):
        await self._client.start()
        await self._client.call("initialize", {
            "protocolVersion": "2024-11-05",
            "clientInfo": {"name": "tldw_acp_harness", "version": "0.1.0"},
            "capabilities": {},
        })
        await self._client.notify("initialized", {})

    async def list_tools(self):
        resp = await self._client.call("tools/list", {})
        return resp.result.get("tools", [])

    async def call_tool(self, name, arguments):
        resp = await self._client.call("tools/call", {"name": name, "arguments": arguments})
        return resp.result
```

### MCPSSETransport

- Connects to `sse_url` via `httpx` async streaming
- Auto-discovers `post_url` from first SSE event (MCP spec convention), or uses explicit `post_url`
- Sends JSON-RPC requests via HTTP POST
- Receives responses/notifications via SSE stream
- Background task reads SSE stream, matches responses to pending request futures by JSON-RPC `id`

Config:
```python
protocol_config = {
    "mcp_transport": "sse",
    "sse_url": "http://localhost:3000/sse",
    "post_url": None,  # auto-discovered or explicit
    "headers": {},
    "timeout_sec": 30,
}
```

### MCPStreamableHTTPTransport

- Single HTTP endpoint, client POSTs JSON-RPC
- Server responds with `application/json` (single) or `text/event-stream` (streaming)
- Adapter handles both response modes transparently

Config:
```python
protocol_config = {
    "mcp_transport": "streamable_http",
    "endpoint": "http://localhost:3000/mcp",
    "headers": {},
    "timeout_sec": 30,
}
```

### Transport Factory

```python
def create_transport(protocol_config: dict) -> MCPTransport:
    # Dispatches by protocol_config["mcp_transport"]: stdio | sse | streamable_http
```

### Tool Refresh

Optional `mcp_refresh_tools: true` in agent config. Default `false` — tools cached from `connect()`. If true, `list_tools()` called before each `send_prompt()`.

---

## 5. Orchestration Modes

### Agent-Driven (`mcp_orchestration: "agent_driven"`)

Two response formats:

**Simple (default, `mcp_structured_response: false`):**
- Call `entry_tool` with `{"messages": messages}`
- Agent returns text content
- Emit single `COMPLETION` event
- Works with any MCP server out of the box

**Structured (opt-in, `mcp_structured_response: true`):**
- Call `entry_tool` with `{"messages": messages}`
- Agent returns `{"steps": [{"type": "tool_call", ...}, {"type": "thinking", ...}, ...]}` in content
- Each step emitted as appropriate AgentEvent
- tldw-specific convention for rich UI integration

### LLM Integration via LLMCaller Abstraction

The LLM-driven runner uses an `LLMCaller` interface rather than directly importing from `LLM_Calls`:

```python
@dataclass
class LLMResponse:
    text: str | None = None
    tool_calls: list[LLMToolCall] = field(default_factory=list)

@dataclass
class LLMToolCall:
    id: str
    name: str
    arguments: dict[str, Any]

class LLMCaller(ABC):
    async def call(self, messages: list[dict], tools: list[dict]) -> LLMResponse:
        """Send messages + tool definitions to LLM, return response."""
```

A default `TldwLLMCaller` implementation wraps tldw's existing `chat_completions` function, translating MCP tool `input_schema` to OpenAI-compatible `parameters` (both are JSON Schema — straightforward mapping). This keeps the runner testable (mock `LLMCaller`) and decoupled from LLM module internals.

### LLM-Driven (`mcp_orchestration: "llm_driven"`)

ReAct loop with ephemeral message history:

```python
async def run(self, messages: list[dict]) -> None:
    tools = self._tools  # cached or refreshed
    history = list(messages)

    for iteration in range(self._max_iterations):
        if self._cancel_event.is_set():
            break

        response = await self._llm_call(history, tools)

        if response.tool_calls:
            for tc in response.tool_calls:
                gate_result = await self._tool_gate.request_approval(
                    self._session_id, tc.name, tc.arguments
                )
                if not gate_result.approved:
                    history.append(tool_error_message(tc, gate_result.reason))
                    await self._emit(TOOL_RESULT, is_error=True, ...)
                    continue

                await self._emit(TOOL_CALL, ...)
                result = await self._transport.call_tool(tc.name, tc.arguments)
                await self._emit(TOOL_RESULT, ...)
                history.append(tool_result_message(tc, result))

        if response.text:
            await self._emit(COMPLETION, text=response.text)
            return

    await self._emit(COMPLETION, stop_reason="max_iterations")
```

### Cancellation

`MCPAdapter` holds `_cancel_event: asyncio.Event`. `cancel()` sets it. Both runners check `_cancel_event.is_set()` between iterations and before tool calls. Mid-LLM-call cancellation via `asyncio.Task.cancel()`.

---

## 6. MCPAdapter Lifecycle

```python
class MCPAdapter(ProtocolAdapter):
    protocol_name = "mcp"

    async def connect(self, config: AdapterConfig) -> None:
        # 1. Create transport from protocol_config via create_transport()
        # 2. Connect transport
        # 3. Discover tools via list_tools()
        # 4. Emit lifecycle:agent_started, then lifecycle:agent_ready
        # 5. Set _connected = True

    async def send_prompt(self, messages, options=None) -> None:
        # 1. Optionally refresh tools if mcp_refresh_tools
        # 2. Clear cancel event
        # 3. Start heartbeat background task (emits heartbeat every 15s)
        # 4. Create appropriate runner (AgentDrivenRunner or LLMDrivenRunner)
        # 5. Emit status_change: idle → working
        # 6. await runner.run(messages)
        # 7. Cancel heartbeat task
        # 8. Emit status_change: working → idle

    async def send_tool_result(self, tool_id, result, is_error) -> None:
        # For future use (sampling support). No-op for now.

    async def cancel(self) -> None:
        # Set _cancel_event

    async def disconnect(self) -> None:
        # 1. Cancel any active runner
        # 2. Close transport
        # 3. Emit lifecycle:agent_exited

    @property
    def is_connected(self) -> bool:
        return self._connected and self._transport is not None and self._transport.is_connected

    @property
    def supports_streaming(self) -> bool:
        return True  # events stream via callback during send_prompt
```

---

## 7. AgentEvent Translation

| MCP Source | AgentEvent Kind | Notes |
|------------|----------------|-------|
| Transport connect success | `lifecycle` (agent_started) | Process spawned / HTTP connected |
| `tools/list` complete | `lifecycle` (agent_ready) | Tools discovered |
| `tools/call` request (outgoing) | `tool_call` | Before calling MCP tool |
| `tools/call` response | `tool_result` | With output, is_error, duration_ms |
| LLM thinking (llm_driven) | `thinking` | From LLM streaming |
| LLM final text | `completion` | End of loop |
| Agent text result (agent_driven) | `completion` | Simple mode |
| Agent steps (agent_driven) | varies | Structured mode, per step type |
| Heartbeat timer | `heartbeat` | Every 15s during send_prompt |
| Transport disconnect | `lifecycle` (agent_exited) | |
| Any error | `error` | code, message, recoverable |

---

## 8. Error Handling

| Failure | Behavior |
|---------|----------|
| Transport connect fails | Raise `RuntimeError` from `connect()` |
| Transport dies mid-session | `error {code: "transport_disconnect", recoverable: true}`, reconnect (max 3, see below) |
| `tools/list` fails | `error {code: "tool_discovery_failed", recoverable: false}` |
| `tools/call` returns error | `tool_result {is_error: true}`, feed to LLM (llm_driven) |
| LLM call fails | `error {code: "llm_error", recoverable: true}`, retry once |
| Max iterations reached | `completion {stop_reason: "max_iterations"}` |
| Governance timeout | Handled by GovernanceFilter (Phase A) |
| Cancel during execution | `status_change {to_status: "cancelled"}` |

### Reconnection Strategy (per transport)

MCPAdapter handles reconnect at the transport-agnostic level: close transport → create new transport → reconnect → re-discover tools. Max 3 attempts with exponential backoff.

| Transport | What "disconnect" means | Reconnect action |
|-----------|------------------------|-------------------|
| Stdio | Process exited unexpectedly | Restart process, re-initialize handshake |
| SSE | SSE stream dropped | Re-establish SSE connection, re-discover POST URL |
| Streamable HTTP | Endpoint unreachable (health check fails) | Retry connection. Individual request failures are retried at the request level, not the transport level. |

---

## 9. Agent Registry Extension

New fields on `AgentRegistryEntry`:

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `mcp_orchestration` | `Literal["agent_driven", "llm_driven"]` | `"agent_driven"` | Who drives tool-call loop |
| `mcp_entry_tool` | `str` | `"execute"` | Entry tool for agent_driven mode |
| `mcp_structured_response` | `bool` | `False` | Whether agent returns steps array |
| `mcp_llm_provider` | `str \| None` | `None` | LLM provider for llm_driven |
| `mcp_llm_model` | `str \| None` | `None` | LLM model for llm_driven |
| `mcp_max_iterations` | `int` | `20` | Max ReAct loop iterations |
| `mcp_refresh_tools` | `bool` | `False` | Re-discover tools before each prompt |

---

## 10. Testing Strategy

### Unit Tests

| Component | Tests |
|-----------|-------|
| `MCPTransport` ABC | Abstract, can't instantiate |
| `MCPStdioTransport` | JSON-RPC framing, initialize handshake, list_tools, call_tool, error handling, process lifecycle |
| `MCPSSETransport` | SSE parsing, POST URL discovery, request/response matching, reconnect |
| `MCPStreamableHTTPTransport` | Single-response and streaming-response, error codes |
| `create_transport()` | Factory dispatch, rejects unknown type |
| `AgentDrivenRunner` | Simple text → completion. Structured steps → events. Errors. |
| `LLMDrivenRunner` | Single-turn. Multi-turn with tools. Max iterations. Cancel. Governance denial. |
| `MCPAdapter` | Connect/disconnect lifecycle, runner delegation, cancel, is_connected, tool refresh |
| `ToolGate` | ABC is abstract, mock implementation |

### Integration Tests

| Scenario | Coverage |
|----------|----------|
| Stdio end-to-end | Mock MCP server → transport → adapter → bus → events |
| LLM-driven loop | Mock transport + mock LLM → 2 tool calls → completion |
| Agent-driven simple | Mock transport text → completion event |
| Agent-driven structured | Mock transport steps → multiple events |
| Governance gate | ToolGate denies → LLM receives denial → adjusts |
| Cancel mid-loop | Cancel after 1st iteration → status_change event |

---

## 11. File Map

| New File | Purpose |
|----------|---------|
| `adapters/mcp_adapter.py` | MCPAdapter implementing ProtocolAdapter |
| `adapters/mcp_transport.py` | MCPTransport ABC + `create_transport()` factory |
| `adapters/mcp_transports/__init__.py` | Transport package exports |
| `adapters/mcp_transports/stdio.py` | MCPStdioTransport (composes ACPStdioClient) |
| `adapters/mcp_transports/sse.py` | MCPSSETransport |
| `adapters/mcp_transports/streamable_http.py` | MCPStreamableHTTPTransport |
| `adapters/mcp_runners.py` | AgentDrivenRunner + LLMDrivenRunner |
| `adapters/mcp_llm_caller.py` | LLMCaller ABC + TldwLLMCaller default implementation |
| `tool_gate.py` | ToolGate ABC + ToolGateResult |

| Modified File | Change |
|---------------|--------|
| `agent_registry.py` | 7 new fields |
| `adapters/__init__.py` | Export MCPAdapter |
| `governance_filter.py` | Add GovernanceToolGate concrete implementation |

---

## Appendix: Design Review Changes

### First Review

| # | Issue | Severity | Resolution |
|---|-------|----------|------------|
| 1 | No return channel from GovernanceFilter to adapter | High | Added ToolGate protocol for llm_driven approval |
| 2 | Invented structured response format | Medium | Default to simple text, structured opt-in |
| 3 | No tool refresh strategy | Low | Optional `mcp_refresh_tools` config |
| 4 | SSE dual-endpoint not clarified | Medium | Auto-discover from SSE stream or explicit `post_url` |
| 5 | MCPOrchestrator god class | Medium | Split into AgentDrivenRunner and LLMDrivenRunner |
| 6 | LLM-driven history unspecified | Medium | Ephemeral message list per-prompt in LLMDrivenRunner |
| 7 | Cancel not specified | Medium | asyncio.Event checked between iterations |

### Final Review

| # | Issue | Severity | Resolution |
|---|-------|----------|------------|
| 8 | GovernanceToolGate concrete location unspecified | Low | Lives in `governance_filter.py`, MCPAdapter imports only ABC |
| 9 | LLM integration underspecified | Medium | Added `LLMCaller` ABC + `TldwLLMCaller` default wrapper |
| 10 | Heartbeat not designed | Low | Background task in `MCPAdapter.send_prompt()`, cancelled on return |
| 11 | Stdio transport duplicates JSON-RPC logic | Medium | Compose `ACPStdioClient` internally instead of reimplementing |
| 12 | HTTP reconnect undefined | Low | Per-transport strategy documented, adapter handles reconnect loop |
