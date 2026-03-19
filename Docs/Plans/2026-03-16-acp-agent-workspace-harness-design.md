# ACP Agent Workspace Harness — Design Document

**Date**: 2026-03-16
**Status**: Approved
**Scope**: Multi-protocol agent harness with event bus architecture, accessible from WebUI/extension via ACP module

---

## 1. Overview

Enable users to run any agent backend from the tldw WebUI/extension through the ACP module. The agent harness supports multiple wire protocols (ACP-stdio, MCP, OpenAI tool-use), provides full transparency with configurable verbosity, and delegates isolation to the existing Sandbox module.

### Key Decisions

| Decision | Choice |
|----------|--------|
| UX model | Dedicated Agent Workspace panel — full interactive, Claude-Code-like experience in the browser |
| Agent backends | Generic protocol adapters, no agent-specific code in the harness |
| Isolation | Local process (single-user) or Sandbox module (Docker/VM for multi-user). Existing Sandbox module is the execution backend. |
| Introspection | Full transparency with configurable verbosity (full/structured/summary) |
| Wire protocols | Multi-protocol from day one: ACP-stdio, MCP, OpenAI tool-use via `ProtocolAdapter` interface |
| Architecture | ACP = user-facing orchestration layer, Sandbox = pure execution backend |
| Protocol translation | Server-side adapters in ACP, uniform `AgentEvent` stream to UI |
| Event architecture | Hybrid Approach 1→2: adapter layer first, event bus introduced when second consumer is wired |
| First deliverable | Protocol adapter layer + event schema, then WebUI |

---

## 2. AgentEvent Schema

The core contract. Every protocol adapter produces these, every consumer reads them.

```
AgentEvent
├── session_id: str
├── sequence: int              # monotonic per session, assigned by bus
├── timestamp: datetime
├── kind: AgentEventKind       # enum
├── payload: dict              # kind-specific, documented not enforced
└── metadata: dict             # optional (adapter name, protocol, latency)
```

### Event Kinds

| Kind | Payload fields |
|------|---------------|
| `thinking` | `text: str`, `is_partial: bool` |
| `tool_call` | `tool_id: str`, `tool_name: str`, `arguments: dict`, `permission_tier: str` |
| `tool_result` | `tool_id: str`, `tool_name: str`, `output: str`, `is_error: bool`, `duration_ms: int` |
| `file_change` | `path: str`, `action: create\|modify\|delete`, `diff: str\|null`, `content: str\|null` |
| `terminal_output` | `command: str`, `output: str`, `exit_code: int\|null`, `is_partial: bool` |
| `permission_request` | `request_id: str`, `tool_name: str`, `arguments: dict`, `tier: str`, `timeout_sec: int` |
| `permission_response` | `request_id: str`, `decision: approve\|deny`, `reason: str\|null` |
| `completion` | `text: str`, `stop_reason: str` |
| `error` | `code: str`, `message: str`, `recoverable: bool` |
| `status_change` | `from_status: str`, `to_status: str` |
| `token_usage` | `prompt_tokens: int`, `completion_tokens: int`, `total_tokens: int` |
| `heartbeat` | `elapsed_sec: int`, `state: thinking\|executing\|waiting` |
| `lifecycle` | `event: agent_started\|agent_ready\|agent_exited\|sandbox_provisioned\|sandbox_destroyed`, `exit_code: int\|null` |

### Design Rationale

- `sequence` is per-session monotonic — enables exactly-once delivery, gap detection, and replay from any point
- `payload` is a dict, not a union type — extensible without breaking consumers that ignore unknown kinds
- `file_change` is first-class — the Agent Workspace needs to show diffs in real-time
- `permission_request`/`permission_response` are events in the stream, not a side-channel
- `heartbeat` distinguishes "agent is working silently" from "adapter is disconnected" — adapters emit every 15s (configurable) while processing
- `lifecycle` tracks agent process and sandbox environment state transitions — enables the UI to show provisioning progress and clean exit vs crash

---

## 3. ProtocolAdapter Interface

```python
class ProtocolAdapter(ABC):
    protocol_name: str  # "stdio", "mcp", "openai_tool_use"

    async def connect(self, config: AdapterConfig) -> None
    async def disconnect(self) -> None
    async def send_prompt(self, messages: list[dict], options: PromptOptions) -> None
    async def send_tool_result(self, tool_id: str, result: str, is_error: bool) -> None
    async def cancel(self) -> None
    is_connected: bool  # property
    supports_streaming: bool  # property
```

### AdapterConfig

```python
@dataclass
class AdapterConfig:
    event_callback: Callable[[AgentEvent], Awaitable[None]]
    session_id: str
    protocol_config: dict  # adapter-specific, validated by the adapter on connect()
```

Each adapter defines and validates its own config shape from `protocol_config`:

| Adapter | Expected `protocol_config` keys |
|---------|-------------------------------|
| `StdioAdapter` | `process: asyncio.subprocess.Process` |
| `MCPAdapter` | `mcp_endpoint: str`, `mcp_transport: "stdio"\|"sse"\|"streamable_http"`, optionally `process` for stdio transport |
| `OpenAIToolUseAdapter` | `api_base_url: str`, `api_key: str\|null`, `model: str`, `tools: list[dict]\|null` |

This keeps `AdapterConfig` generic — adding a 4th protocol doesn't change the dataclass.

### `send_prompt()` Contract

`send_prompt()` is async and may run for an extended period — the agent's full turn, which can involve many internal tool calls and reasoning steps. Events stream via `event_callback` throughout execution. The method returns when the agent's turn is complete (final `completion` event) or on unrecoverable error. Callers should not assume it returns quickly.

### Three Adapters

**StdioAdapter**: Wraps existing `ACPStdioClient`. JSON-framed messages over stdin/stdout. Works with Claude Code, Aider, any CLI agent. The agent drives its own execution loop internally.

**MCPAdapter**: Acts as an MCP **client** connecting to the agent's MCP **server**. The agent exposes its capabilities (tools, resources) via MCP; the adapter discovers and invokes them. Supports stdio, SSE, and streamable HTTP transports. Leverages patterns from existing `MCP_unified` module. Note: agents that want to *consume* tldw's tools connect to tldw's existing MCP Unified module separately — that is out of scope for the adapter layer.

**OpenAIToolUseAdapter**: HTTP client to OpenAI-compatible chat completions endpoint. Drives a multi-turn loop internally: send prompt → receive streaming tool_call chunks → execute tools (via ToolExecutor) → send results back → repeat until final completion. Works with vLLM, Ollama, LiteLLM, any compatible server.

### Tool Execution Ownership

Different agents handle tool execution differently. The `tool_execution_mode` field on the agent registry entry determines who executes tools:

| Mode | Behavior | Typical agents |
|------|----------|---------------|
| `agent_side` | Agent executes tools internally (bash, file I/O, etc.). Adapter observes and reports `tool_call`/`tool_result` events. GovernanceFilter can block by withholding approval before the agent acts. | Claude Code, Aider, Open Interpreter |
| `server_side` | Agent requests tool calls, server executes them via `ToolExecutor`, sends results back via `adapter.send_tool_result()`. | OpenAI-compatible models, MCP agents exposing tool requests |
| `hybrid` | Agent has local tools it executes itself, plus server-provided tools (e.g., RAG search, media ingestion). Tool routing by name prefix or registry lookup. | Custom agents with tldw integration |

```python
class ToolExecutor(ABC):
    """Executes tools on behalf of agents in server_side/hybrid mode."""

    async def execute(self, tool_name: str, arguments: dict) -> ToolResult:
        """Run a tool and return its result."""

    async def list_tools(self) -> list[ToolDefinition]:
        """Return available server-side tools."""
```

The default `ToolExecutor` implementation delegates to tldw's existing tool registry (RAG search, media processing, etc.). Custom executors can be registered per-session.

### Adapter Instantiation

```
Agent Registry Entry (protocol + tool_execution_mode) → AdapterFactory → ProtocolAdapter instance
If sandboxed: Sandbox module provides container → adapter connects to process/endpoint inside
If local: spawn process directly → adapter connects
ToolExecutor wired based on tool_execution_mode
```

---

## 4. Session Event Bus

Per-session async event fan-out. Starts as `asyncio.Queue` with fan-out, grows into the system backbone.

**Important**: GovernanceFilter is a **pipeline stage** between the adapter and the bus, not a bus consumer. It must be able to intercept `tool_call` events and hold them (preventing downstream delivery) until a permission decision arrives. A subscriber pattern cannot block delivery to other subscribers.

```
ProtocolAdapter → GovernanceFilter (intercepts, gates tool_calls) → SessionEventBus → fan-out → Consumers
                        ▲                                                ▲
                        │ permission_response                            │ inject()
                        └────────────────────────────────────────────────┘
```

The adapter's `event_callback` points to `GovernanceFilter.process()`, which either forwards events to the bus immediately (most events) or holds `tool_call` events pending approval. When a `permission_response` arrives via `bus.inject()`, the bus routes it back to the GovernanceFilter, which resolves the pending tool and forwards the original `tool_call` to the bus.

### SessionEventBus API

```python
class SessionEventBus:
    def __init__(self, session_id: str, max_buffer: int = 10_000)
    async def publish(self, event: AgentEvent) -> None        # assign sequence, distribute
    def subscribe(self, consumer_id: str, from_sequence: int = 0) -> asyncio.Queue
    def unsubscribe(self, consumer_id: str) -> None
    async def inject(self, event: AgentEvent) -> None          # external events (governance)
    def snapshot(self, from_sequence: int = 0) -> list[AgentEvent]  # replay for late joiners
```

### Design Rationale

- One bus per session, not global — sessions are independent
- Bounded history buffer (configurable per session, default 10k events) — enables late-join replay without unbounded memory
- Backpressure via bounded subscriber queues (1000 events) — slow consumers evicted after 30s
- `inject()` for external events — governance decisions flow back into the same stream
- No persistence in the bus — `AuditLogger` consumer handles durable storage

### Replay Fallback for Long Sessions

For long-running sessions that exceed the bus buffer (e.g., 500+ tool calls with verbose output), a WebSocket reconnecting after buffer rotation would get an incomplete replay. Two-tier replay strategy:

1. **Fast path**: `bus.snapshot(from_sequence)` — serves from in-memory ring buffer. Works for recent events.
2. **Slow path**: If `from_sequence` is older than the buffer's earliest event, `WSBroadcaster` falls back to replaying from `ACP_Audit_DB` (the `AuditLogger` consumer's durable store). Slower but complete.

The `WSBroadcaster` detects the gap (requested sequence < buffer's min sequence) and transparently switches to the slow path. The client sees a seamless stream regardless of source.

### GovernanceFilter (Pipeline Stage)

```python
class GovernanceFilter:
    """Pipeline stage between adapter and bus. NOT a bus consumer."""

    def __init__(self, bus: SessionEventBus, policy: PermissionPolicy):
        self._bus = bus
        self._policy = policy
        self._pending: dict[str, PendingToolCall] = {}  # request_id → held tool_call

    async def process(self, event: AgentEvent) -> None:
        """Called by adapter's event_callback. Gates tool_calls, forwards everything else."""
        if event.kind == "tool_call":
            tier = self._policy.resolve_tier(event.payload["tool_name"])
            if tier == "auto":
                await self._bus.publish(event)  # auto-approved, pass through
            else:
                request_id = str(uuid4())
                self._pending[request_id] = PendingToolCall(event, tier)
                await self._bus.publish(AgentEvent(kind="permission_request", ...))
        else:
            await self._bus.publish(event)  # non-tool events pass through immediately

    async def on_permission_response(self, request_id: str, decision: str) -> None:
        """Called when bus routes a permission_response back to the filter."""
        pending = self._pending.pop(request_id)
        if decision == "approve":
            await self._bus.publish(pending.event)  # release the held tool_call
        else:
            await self._bus.publish(AgentEvent(kind="tool_result", payload={
                "tool_id": pending.event.payload["tool_id"],
                "is_error": True, "output": f"Permission denied: {decision}"
            }))
```

### Bus Consumers

| Consumer | Role |
|----------|------|
| `WSBroadcaster` | Forwards events to WebSockets with verbosity filtering |
| `AuditLogger` | Persists events to `ACP_Audit_DB`, batched writes (flush every 100 events or 5s) |
| `MetricsRecorder` | Updates Prometheus counters/histograms from `token_usage`, `tool_call`, `error` events |
| `OrchestratorSink` | Updates orchestration task/run state (only active for orchestrated sessions) |

All bus consumers are non-blocking. GovernanceFilter is the only component that can hold events, and it operates as a pipeline stage before the bus, not as a subscriber.

### Consumer Interface

```python
class EventConsumer(ABC):
    consumer_id: str
    async def on_event(self, event: AgentEvent) -> None
    async def start(self, bus: SessionEventBus) -> None
    async def stop(self) -> None
```

### Governance Flow

1. Adapter emits `tool_call` with `tool_name` → delivered to `GovernanceFilter.process()`
2. GovernanceFilter checks policy, resolves permission tier
3. If `auto`: forwards `tool_call` to bus immediately
4. If `batch`/`individual`: holds `tool_call` in pending map, publishes `permission_request` to bus
5. `WSBroadcaster` (bus consumer) forwards `permission_request` to WebUI
6. User clicks approve → server calls `governance_filter.on_permission_response()`
7. GovernanceFilter releases held `tool_call` to bus
8. For `agent_side` execution: agent already has the tool result (it executed locally); adapter emits `tool_result`
9. For `server_side` execution: `ToolExecutor` runs the tool, result sent back via `adapter.send_tool_result()`, adapter emits `tool_result`
10. All bus consumers see `tool_result` normally

---

## 5. ACPRunnerClient Refactor

Evolves from god object to thin coordinator.

### New Architecture

```
WebSocket/REST → ACPRunnerClient → SessionEventBus → consumers (WS, audit, metrics, orchestrator)
                       │                  ▲
                       │                  │ events (gated)
                       │           GovernanceFilter (pipeline stage)
                       │                  ▲
                       ▼                  │ raw events
                 ProtocolAdapter ─────────┘
                       │
                       ▼
                 subprocess / HTTP endpoint / MCP server
                       │
                 (ToolExecutor for server_side/hybrid mode)
```

### What Moves Out

- Direct `ACPStdioClient` usage → replaced by `ProtocolAdapter`
- Inline governance → `GovernanceFilter` pipeline stage
- Inline WebSocket routing → `WSBroadcaster` consumer
- Inline audit recording → `AuditLogger` consumer
- Inline metrics → `MetricsRecorder` consumer
- `PendingPermission` map → `GovernanceFilter`
- `SessionWebSocketRegistry` → `WSBroadcaster`

### What Stays

- Session lifecycle (create, close, teardown)
- Adapter + bus + consumer wiring
- Sandbox delegation via `SandboxBridge`
- Session state map
- Fork/reconciliation

### Migration Path (No Big Bang)

- **Phase A**: `StdioAdapter` wraps existing `ACPStdioClient`. All 133 tests pass, behavior identical.
- **Phase B**: `SessionEventBus` + `GovernanceFilter`. Permission logic moves out of runner.
- **Phase C**: WSBroadcaster, AuditLogger, MetricsRecorder become consumers. Runner is thin.
- **Phase D**: Add `MCPAdapter` and `OpenAIToolUseAdapter`. They just work.

### Backward Compatibility

- All existing REST/WebSocket endpoints unchanged
- `agents.yaml` entries without `protocol` default to `"stdio"`
- Existing session store, audit DB, metrics untouched

---

## 6. Sandbox Integration

ACP delegates to the Sandbox module for isolated execution via `SandboxBridge`.

### SandboxBridge

```python
class SandboxBridge:
    def __init__(self, sandbox_service: SandboxService)
    async def provision(self, request: SandboxProvisionRequest) -> SandboxHandle
    async def teardown(self, handle: SandboxHandle) -> None
    async def snapshot(self, handle: SandboxHandle) -> str
    async def restore(self, handle: SandboxHandle, snapshot_id: str) -> None
```

### SandboxHandle

```python
@dataclass
class SandboxHandle:
    sandbox_session_id: str
    run_id: str
    process_stdin: StreamWriter | None    # for stdio adapter
    process_stdout: StreamReader | None   # for stdio adapter
    endpoint: str | None                  # for MCP/OpenAI adapter
    ssh_endpoint: str | None              # for terminal access
```

### Adapter + Sandbox Connection

| Protocol | How it connects through sandbox |
|----------|-------------------------------|
| stdio | Container starts agent binary, stdin/stdout piped to adapter |
| MCP | Container starts agent in MCP server mode, port mapped, adapter connects to endpoint |
| OpenAI tool-use | Container starts OpenAI-compatible server, adapter sends to endpoint |

### Runtime Selection

| Mode | Runtime | Rationale |
|------|---------|-----------|
| Single-user, local | None (no sandbox) | Direct process, adapter connects locally |
| Single-user, wants isolation | Docker or seatbelt | User opts in |
| Multi-user | Docker (default) | Always sandboxed |
| Multi-user, heavy workload | Firecracker / Lima | Admin configures per-agent |

### Deprecation

`sandbox_runner_client.py` is deprecated. `SandboxBridge` replaces it as the integration seam.

---

## 7. Agent Registry Extension

### New YAML Fields

```yaml
agents:
  - type: claude-code
    protocol: stdio                        # NEW: stdio | mcp | openai_tool_use
    tool_execution_mode: agent_side        # NEW: agent executes tools internally
    command: claude
    args: ["--chat"]
    # ... existing fields ...

  - type: local-mcp-agent
    protocol: mcp
    tool_execution_mode: server_side       # NEW: server executes tools via ToolExecutor
    mcp_transport: stdio                   # NEW: stdio | sse | streamable_http
    command: /usr/local/bin/my-agent

  - type: ollama-agent
    protocol: openai_tool_use
    tool_execution_mode: server_side       # NEW: server drives the tool call loop
    api_base_url: http://localhost:11434/v1  # NEW
    model: llama3.1                          # NEW
    tools_from: auto                         # NEW: auto | static | none
    sandbox: required                        # NEW: required | optional | none
    trust_level: untrusted                   # NEW: untrusted | standard | trusted

  - type: custom-hybrid-agent
    protocol: stdio
    tool_execution_mode: hybrid            # NEW: agent has local tools + server-provided tools
    command: /usr/local/bin/my-hybrid-agent
    sandbox: optional
```

### New Fields on AgentRegistryEntry

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `protocol` | `stdio \| mcp \| openai_tool_use` | `stdio` | Which adapter to use |
| `tool_execution_mode` | `agent_side \| server_side \| hybrid` | `agent_side` | Who executes tools (see Section 3) |
| `mcp_transport` | `stdio \| sse \| streamable_http` | `stdio` | MCP transport variant |
| `api_base_url` | `str \| null` | null | HTTP-based protocol endpoint |
| `model` | `str \| null` | null | Model ID for OpenAI adapter |
| `tools_from` | `auto \| static \| none` | `auto` | Tool definition source |
| `sandbox` | `required \| optional \| none` | `none` | Sandbox enforcement |
| `trust_level` | `untrusted \| standard \| trusted` | `standard` | Default sandbox trust |

### Availability Checks Per-Protocol

- `stdio`: binary on PATH (existing)
- `mcp`: binary on PATH or endpoint reachable
- `openai_tool_use`: endpoint reachable + model exists

---

## 8. WebUI Event Contract

### Verbosity Levels

| Level | Events delivered |
|-------|----------------|
| `full` | Everything unfiltered |
| `structured` | `tool_call`, `tool_result`, `file_change`, `permission_*`, `completion`, `error`, `status_change`. Thinking summarized. Terminal grouped. |
| `summary` | `completion`, `error`, `permission_*`, `status_change` only |

### WebSocket Protocol

```json
// Client → Server: configure on connect
{"type": "configure", "verbosity": "full", "replay_from_sequence": 0}

// Client → Server: change verbosity mid-session
{"type": "configure", "verbosity": "structured"}

// Client → Server: permission approval
{"type": "permission_response", "request_id": "r1", "decision": "approve"}

// Server → Client: AgentEvent stream (filtered by verbosity)
{"session_id": "...", "sequence": 42, "kind": "tool_call", "payload": {...}, ...}
```

### Design Rationale

- Verbosity is a UI concern — bus carries all events, WSBroadcaster filters per-connection
- Replay on reconnect via `replay_from_sequence`
- Reuses existing `WS /acp/sessions/{session_id}/stream` endpoint

---

## 9. Error Handling

### Adapter Failures

Adapter disconnect → `error {code: "adapter_disconnect", recoverable: true}` → ACPRunnerClient retries (max 3, exponential backoff) → if exhausted: `error {recoverable: false}`, session fails.

### Sandbox Crashes

Container exits → SandboxBridge detects → `error {code: "sandbox_crash", recoverable: false}` → session cleaned up, audit preserved → UI can offer restore-and-retry if snapshot exists.

### Backpressure

Subscriber queue full (1000 events) → warning logged → after 30s still full: consumer evicted → WSBroadcaster eviction closes WebSocket with 1008 → client reconnects with replay.

### Permission Timeout

`permission_request` unanswered for `timeout_sec` (default 300s) → `permission_response {decision: "deny", reason: "timeout"}` → agent continues without the tool. No session termination.

---

## 10. Security

| Concern | Mitigation |
|---------|-----------|
| Arbitrary endpoint connection | `api_base_url` validated against allowlist in multi-user mode |
| Event flooding | Bus enforces per-second rate limit (default 1000/s), adapter disconnected if exceeded |
| Payload injection | Consumers treat payload as untrusted. WSBroadcaster sanitizes. AuditLogger parameterizes DB writes. |
| Sandbox escape via adapter | Adapters receive structured events only, no shell access. Sandbox enforces network policy independently. |
| Cross-user leakage | Bus is per-session, sessions are per-user. Auth checked at WS connect and REST endpoints. |
| API key leakage | Adapters strip secrets from tool_call arguments. Audit logger redacts known secret patterns. |

---

## 11. Testing Strategy

### Unit Tests

| Component | Focus |
|-----------|-------|
| `AgentEvent` | Serialization, all 13 payload shapes, sequence ordering, heartbeat/lifecycle |
| `StdioAdapter` | Message framing, event translation, disconnect, heartbeat emission |
| `MCPAdapter` | All 3 transports, tool discovery, event mapping, agent-as-MCP-server model |
| `OpenAIToolUseAdapter` | Streaming chunks, multi-turn tool call loop, errors, long-running `send_prompt()` |
| `SessionEventBus` | Fan-out, ordering, replay, backpressure, inject, configurable buffer size |
| `GovernanceFilter` | Pipeline stage behavior: hold/release tool_calls, all permission tiers, timeout, policy, denied tool result emission |
| `ToolExecutor` | Server-side tool execution, tool registry, error handling |
| `WSBroadcaster` | All 3 verbosity levels, reconnect replay, eviction, audit DB fallback for old sequences |
| `SandboxBridge` | Provision/teardown, trust mapping, snapshot/restore |
| `AdapterFactory` | Protocol resolution, plugin registration, tool_execution_mode wiring |

### Integration Tests

| Scenario | Coverage |
|----------|----------|
| Stdio end-to-end | Mock agent binary → StdioAdapter → GovernanceFilter → bus → WS |
| MCP end-to-end | Mock MCP server → MCPAdapter → GovernanceFilter → bus → WS |
| OpenAI end-to-end | Mock OpenAI server → OpenAIToolUseAdapter → ToolExecutor → bus → completion loop |
| Permission flow (agent_side) | tool_call → GovernanceFilter holds → approval → release → agent executes |
| Permission flow (server_side) | tool_call → GovernanceFilter holds → approval → ToolExecutor executes → result back to adapter |
| Sandbox provisioning | SandboxBridge → Docker → adapter connects inside container → events flow out |
| Reconnect replay (fast) | Connect → events → disconnect → reconnect with recent sequence → bus buffer replay |
| Reconnect replay (slow) | Connect → many events → buffer rotates → disconnect → reconnect with old sequence → audit DB fallback |
| Heartbeat liveness | Long tool execution → adapter emits heartbeats → UI receives them → no false disconnect |
| Lifecycle events | Session create → sandbox_provisioned → agent_started → agent_ready → work → agent_exited |

### Existing Tests Preserved

- All 133 ACP tests pass through Phase A (StdioAdapter wraps existing client)
- All 100 Sandbox tests untouched (SandboxBridge uses public SandboxService API)

---

## Appendix: Design Review Changes

The following issues were identified during design review and incorporated into this document:

| # | Issue | Severity | Resolution |
|---|-------|----------|------------|
| 1 | GovernanceFilter as bus subscriber can't block event delivery | High | Restructured as pipeline stage between adapter and bus (Section 4) |
| 2 | Tool execution ownership undefined (who runs tools?) | High | Added `ToolExecutor` interface + `tool_execution_mode` registry field (Section 3) |
| 3 | MCP adapter role ambiguity (client vs server?) | Medium | Explicitly documented agent-as-MCP-server model (Section 3) |
| 4 | OpenAI adapter multi-turn loop not reflected in interface | Low | Documented `send_prompt()` long-running contract (Section 3) |
| 5 | No heartbeat for long-running silent agents | Medium | Added `heartbeat` event kind (Section 2) |
| 6 | Bus buffer exhaustion on long sessions breaks replay | Medium | Added audit DB fallback as slow-path replay (Section 4) |
| 7 | Flat `AdapterConfig` optional fields won't scale to N protocols | Low | Replaced with `protocol_config: dict` validated per-adapter (Section 3) |
| 8 | No lifecycle events for agent/sandbox state transitions | Medium | Added `lifecycle` event kind (Section 2) |
