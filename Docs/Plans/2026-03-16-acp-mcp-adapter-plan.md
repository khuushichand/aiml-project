# ACP MCP Adapter (Phase B) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an MCPAdapter with three transports (stdio/SSE/streamable HTTP), configurable orchestration (agent_driven/llm_driven), ToolGate governance integration, and LLMCaller abstraction.

**Architecture:** MCPAdapter implements ProtocolAdapter. It creates an MCPTransport (stdio/SSE/streamable_http), discovers tools, then delegates to AgentDrivenRunner or LLMDrivenRunner. LLMDrivenRunner uses ToolGate for governance approval before executing tools. All events flow via the Phase A event_callback → GovernanceFilter → SessionEventBus → consumers pipeline.

**Tech Stack:** Python 3.10+, asyncio, httpx (for HTTP transports), existing ACPStdioClient (for stdio transport), existing Phase A infrastructure.

**Design Doc:** `Docs/Plans/2026-03-16-acp-mcp-adapter-design.md`

---

## Task Order & Dependencies

```
Task 1: ToolGate ABC + ToolGateResult
Task 2: MCPTransport ABC + create_transport() factory
Task 3: MCPStdioTransport (composes ACPStdioClient)
Task 4: MCPSSETransport
Task 5: MCPStreamableHTTPTransport
Task 6: LLMCaller ABC + LLMResponse/LLMToolCall
Task 7: AgentDrivenRunner
Task 8: LLMDrivenRunner
Task 9: MCPAdapter (wires everything together)
Task 10: Agent Registry Extension (7 new fields)
Task 11: GovernanceToolGate concrete implementation
Task 12: Verify all existing ACP tests pass
```

All paths under `tldw_Server_API/app/core/Agent_Client_Protocol/` unless noted.

---

### Task 1: ToolGate ABC + ToolGateResult

**Files:**
- Create: `tldw_Server_API/app/core/Agent_Client_Protocol/tool_gate.py`
- Test: `tldw_Server_API/tests/Agent_Client_Protocol/test_tool_gate.py`

**Step 1: Write the failing test**

```python
# tldw_Server_API/tests/Agent_Client_Protocol/test_tool_gate.py
"""Unit tests for ToolGate ABC and ToolGateResult."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_tool_gate_result_defaults():
    from tldw_Server_API.app.core.Agent_Client_Protocol.tool_gate import ToolGateResult

    r = ToolGateResult(approved=True)
    assert r.approved is True
    assert r.reason is None


def test_tool_gate_result_with_reason():
    from tldw_Server_API.app.core.Agent_Client_Protocol.tool_gate import ToolGateResult

    r = ToolGateResult(approved=False, reason="too dangerous")
    assert r.approved is False
    assert r.reason == "too dangerous"


def test_tool_gate_is_abstract():
    from tldw_Server_API.app.core.Agent_Client_Protocol.tool_gate import ToolGate

    with pytest.raises(TypeError):
        ToolGate()


@pytest.mark.asyncio
async def test_tool_gate_concrete_implementation():
    """A concrete ToolGate should be callable."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.tool_gate import ToolGate, ToolGateResult

    class AlwaysApprove(ToolGate):
        async def request_approval(self, session_id, tool_name, arguments):
            return ToolGateResult(approved=True)

    gate = AlwaysApprove()
    result = await gate.request_approval("s1", "bash", {"cmd": "ls"})
    assert result.approved is True
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_tool_gate.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write implementation**

```python
# tldw_Server_API/app/core/Agent_Client_Protocol/tool_gate.py
"""ToolGate — approval interface between adapter and governance layer."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolGateResult:
    """Result of a tool approval request."""
    approved: bool
    reason: str | None = None


class ToolGate(ABC):
    """Abstract approval gate for tool execution.

    The adapter calls ``request_approval()`` before executing a tool.
    The concrete implementation interacts with GovernanceFilter to
    determine whether the tool call is allowed.
    """

    @abstractmethod
    async def request_approval(
        self,
        session_id: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ToolGateResult:
        """Block until governance decision. Returns approved/denied."""
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_tool_gate.py -v`
Expected: 4 PASSED

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Agent_Client_Protocol/tool_gate.py \
       tldw_Server_API/tests/Agent_Client_Protocol/test_tool_gate.py
git commit -m "feat(acp): add ToolGate ABC and ToolGateResult"
```

---

### Task 2: MCPTransport ABC + create_transport() Factory

**Files:**
- Create: `tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_transport.py`
- Test: `tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_transport.py`

**Step 1: Write the failing test**

```python
# tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_transport.py
"""Unit tests for MCPTransport ABC and create_transport factory."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_mcp_transport_is_abstract():
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_transport import MCPTransport

    with pytest.raises(TypeError):
        MCPTransport()


def test_create_transport_unknown_raises():
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_transport import create_transport

    with pytest.raises(ValueError, match="Unknown MCP transport"):
        create_transport({"mcp_transport": "carrier_pigeon"})


def test_create_transport_stdio():
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_transport import create_transport
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_transports.stdio import MCPStdioTransport

    transport = create_transport({
        "mcp_transport": "stdio",
        "command": "echo",
        "args": ["hello"],
    })
    assert isinstance(transport, MCPStdioTransport)


def test_create_transport_sse():
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_transport import create_transport
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_transports.sse import MCPSSETransport

    transport = create_transport({
        "mcp_transport": "sse",
        "sse_url": "http://localhost:3000/sse",
    })
    assert isinstance(transport, MCPSSETransport)


def test_create_transport_streamable_http():
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_transport import create_transport
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_transports.streamable_http import MCPStreamableHTTPTransport

    transport = create_transport({
        "mcp_transport": "streamable_http",
        "endpoint": "http://localhost:3000/mcp",
    })
    assert isinstance(transport, MCPStreamableHTTPTransport)
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_transport.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write implementation**

Create the transport ABC and factory. Also create stub transport classes so the factory tests pass (full implementations come in Tasks 3-5).

```python
# tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_transport.py
"""MCPTransport ABC and create_transport() factory."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class MCPTransport(ABC):
    """Abstract transport for communicating with an MCP server."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish transport connection and perform MCP handshake."""

    @abstractmethod
    async def close(self) -> None:
        """Close the transport connection."""

    @abstractmethod
    async def list_tools(self) -> list[dict[str, Any]]:
        """Discover tools from the MCP server."""

    @abstractmethod
    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool on the MCP server."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the transport is healthy."""

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Whether the transport has an active connection."""


def create_transport(protocol_config: dict[str, Any]) -> MCPTransport:
    """Create the appropriate MCPTransport from protocol_config."""
    transport_type = protocol_config.get("mcp_transport", "stdio")

    if transport_type == "stdio":
        from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_transports.stdio import MCPStdioTransport
        return MCPStdioTransport(
            command=protocol_config["command"],
            args=protocol_config.get("args", []),
            env=protocol_config.get("env", {}),
        )
    elif transport_type == "sse":
        from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_transports.sse import MCPSSETransport
        return MCPSSETransport(
            sse_url=protocol_config["sse_url"],
            post_url=protocol_config.get("post_url"),
            headers=protocol_config.get("headers", {}),
            timeout_sec=protocol_config.get("timeout_sec", 30),
        )
    elif transport_type == "streamable_http":
        from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_transports.streamable_http import MCPStreamableHTTPTransport
        return MCPStreamableHTTPTransport(
            endpoint=protocol_config["endpoint"],
            headers=protocol_config.get("headers", {}),
            timeout_sec=protocol_config.get("timeout_sec", 30),
        )
    else:
        raise ValueError(f"Unknown MCP transport: {transport_type!r}")
```

Create the `mcp_transports` package with stub implementations:

```python
# tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_transports/__init__.py
"""MCP transport implementations."""
```

```python
# tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_transports/stdio.py
"""MCPStdioTransport — stub, full implementation in Task 3."""
from __future__ import annotations
from typing import Any
from ..mcp_transport import MCPTransport


class MCPStdioTransport(MCPTransport):
    """MCP transport over stdio using ACPStdioClient."""

    def __init__(self, command: str, args: list[str] | None = None, env: dict[str, str] | None = None) -> None:
        self._command = command
        self._args = args or []
        self._env = env or {}
        self._connected = False

    async def connect(self) -> None: raise NotImplementedError
    async def close(self) -> None: raise NotImplementedError
    async def list_tools(self) -> list[dict[str, Any]]: raise NotImplementedError
    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]: raise NotImplementedError
    async def health_check(self) -> bool: raise NotImplementedError
    @property
    def is_connected(self) -> bool: return self._connected
```

```python
# tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_transports/sse.py
"""MCPSSETransport — stub, full implementation in Task 4."""
from __future__ import annotations
from typing import Any
from ..mcp_transport import MCPTransport


class MCPSSETransport(MCPTransport):
    """MCP transport over SSE + HTTP POST."""

    def __init__(self, sse_url: str, post_url: str | None = None,
                 headers: dict[str, str] | None = None, timeout_sec: int = 30) -> None:
        self._sse_url = sse_url
        self._post_url = post_url
        self._headers = headers or {}
        self._timeout_sec = timeout_sec
        self._connected = False

    async def connect(self) -> None: raise NotImplementedError
    async def close(self) -> None: raise NotImplementedError
    async def list_tools(self) -> list[dict[str, Any]]: raise NotImplementedError
    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]: raise NotImplementedError
    async def health_check(self) -> bool: raise NotImplementedError
    @property
    def is_connected(self) -> bool: return self._connected
```

```python
# tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_transports/streamable_http.py
"""MCPStreamableHTTPTransport — stub, full implementation in Task 5."""
from __future__ import annotations
from typing import Any
from ..mcp_transport import MCPTransport


class MCPStreamableHTTPTransport(MCPTransport):
    """MCP transport over streamable HTTP."""

    def __init__(self, endpoint: str, headers: dict[str, str] | None = None,
                 timeout_sec: int = 30) -> None:
        self._endpoint = endpoint
        self._headers = headers or {}
        self._timeout_sec = timeout_sec
        self._connected = False

    async def connect(self) -> None: raise NotImplementedError
    async def close(self) -> None: raise NotImplementedError
    async def list_tools(self) -> list[dict[str, Any]]: raise NotImplementedError
    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]: raise NotImplementedError
    async def health_check(self) -> bool: raise NotImplementedError
    @property
    def is_connected(self) -> bool: return self._connected
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_transport.py -v`
Expected: 5 PASSED

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_transport.py \
       tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_transports/ \
       tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_transport.py
git commit -m "feat(acp): add MCPTransport ABC, create_transport factory, and transport stubs"
```

---

### Task 3: MCPStdioTransport (Full Implementation)

**Files:**
- Modify: `tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_transports/stdio.py`
- Test: `tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_stdio_transport.py`

**Context:** Composes `ACPStdioClient` internally. Uses `client.call()` for JSON-RPC methods: `initialize`, `tools/list`, `tools/call`. Uses `client.notify()` for `initialized`.

**Step 1: Write the failing test**

```python
# tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_stdio_transport.py
"""Unit tests for MCPStdioTransport."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tldw_Server_API.app.core.Agent_Client_Protocol.stdio_client import ACPMessage

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.is_running = True
    return client


@pytest.mark.asyncio
async def test_stdio_transport_connect_performs_handshake(mock_client):
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_transports.stdio import MCPStdioTransport

    mock_client.call.return_value = ACPMessage(jsonrpc="2.0", result={
        "protocolVersion": "2024-11-05",
        "serverInfo": {"name": "test-server"},
        "capabilities": {},
    })

    with patch.object(MCPStdioTransport, '_create_client', return_value=mock_client):
        transport = MCPStdioTransport(command="test-agent", args=["--mcp"])
        transport._client = mock_client
        await transport.connect()

    assert transport.is_connected is True
    # Verify initialize call
    mock_client.start.assert_awaited_once()
    init_call = mock_client.call.call_args_list[0]
    assert init_call[0][0] == "initialize"
    assert "protocolVersion" in init_call[0][1]
    # Verify initialized notification
    mock_client.notify.assert_awaited_once_with("initialized", {})


@pytest.mark.asyncio
async def test_stdio_transport_list_tools(mock_client):
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_transports.stdio import MCPStdioTransport

    mock_client.call.return_value = ACPMessage(jsonrpc="2.0", result={
        "tools": [
            {"name": "search", "description": "Search docs", "inputSchema": {"type": "object"}},
            {"name": "read", "description": "Read file", "inputSchema": {"type": "object"}},
        ]
    })

    transport = MCPStdioTransport(command="test-agent")
    transport._client = mock_client
    transport._connected = True

    tools = await transport.list_tools()
    assert len(tools) == 2
    assert tools[0]["name"] == "search"
    mock_client.call.assert_awaited_with("tools/list", {})


@pytest.mark.asyncio
async def test_stdio_transport_call_tool(mock_client):
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_transports.stdio import MCPStdioTransport

    mock_client.call.return_value = ACPMessage(jsonrpc="2.0", result={
        "content": [{"type": "text", "text": "found 3 results"}],
        "isError": False,
    })

    transport = MCPStdioTransport(command="test-agent")
    transport._client = mock_client
    transport._connected = True

    result = await transport.call_tool("search", {"query": "hello"})
    assert result["content"][0]["text"] == "found 3 results"
    mock_client.call.assert_awaited_with("tools/call", {"name": "search", "arguments": {"query": "hello"}})


@pytest.mark.asyncio
async def test_stdio_transport_close(mock_client):
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_transports.stdio import MCPStdioTransport

    transport = MCPStdioTransport(command="test-agent")
    transport._client = mock_client
    transport._connected = True

    await transport.close()
    mock_client.close.assert_awaited_once()
    assert transport.is_connected is False


@pytest.mark.asyncio
async def test_stdio_transport_health_check(mock_client):
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_transports.stdio import MCPStdioTransport

    transport = MCPStdioTransport(command="test-agent")
    transport._client = mock_client
    transport._connected = True
    mock_client.is_running = True

    assert await transport.health_check() is True

    mock_client.is_running = False
    assert await transport.health_check() is False
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_stdio_transport.py -v`
Expected: FAIL — `NotImplementedError` from stub

**Step 3: Replace stub with full implementation**

Replace the content of `mcp_transports/stdio.py` with:

```python
# tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_transports/stdio.py
"""MCPStdioTransport — MCP over stdio, composing ACPStdioClient."""
from __future__ import annotations

from typing import Any

from loguru import logger

from tldw_Server_API.app.core.Agent_Client_Protocol.stdio_client import ACPStdioClient
from ..mcp_transport import MCPTransport

_MCP_PROTOCOL_VERSION = "2024-11-05"
_CLIENT_INFO = {"name": "tldw_acp_harness", "version": "0.1.0"}


class MCPStdioTransport(MCPTransport):
    """MCP transport over stdio using ACPStdioClient for JSON-RPC framing."""

    def __init__(
        self,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self._command = command
        self._args = args or []
        self._env = env or {}
        self._client: ACPStdioClient | None = None
        self._connected = False

    def _create_client(self) -> ACPStdioClient:
        return ACPStdioClient(self._command, self._args, self._env)

    async def connect(self) -> None:
        if self._client is None:
            self._client = self._create_client()
        await self._client.start()
        await self._client.call("initialize", {
            "protocolVersion": _MCP_PROTOCOL_VERSION,
            "clientInfo": _CLIENT_INFO,
            "capabilities": {},
        })
        await self._client.notify("initialized", {})
        self._connected = True
        logger.info("MCPStdioTransport: connected to {}", self._command)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
        self._connected = False

    async def list_tools(self) -> list[dict[str, Any]]:
        if self._client is None:
            raise RuntimeError("Not connected")
        resp = await self._client.call("tools/list", {})
        return resp.result.get("tools", []) if resp.result else []

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError("Not connected")
        resp = await self._client.call("tools/call", {"name": tool_name, "arguments": arguments})
        return resp.result if resp.result else {}

    async def health_check(self) -> bool:
        if self._client is None:
            return False
        return getattr(self._client, "is_running", False)

    @property
    def is_connected(self) -> bool:
        if not self._connected or self._client is None:
            return False
        return getattr(self._client, "is_running", False)
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_stdio_transport.py -v`
Expected: 5 PASSED

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_transports/stdio.py \
       tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_stdio_transport.py
git commit -m "feat(acp): implement MCPStdioTransport composing ACPStdioClient"
```

---

### Task 4: MCPSSETransport (Full Implementation)

**Files:**
- Modify: `tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_transports/sse.py`
- Test: `tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_sse_transport.py`

**Context:** Uses `httpx.AsyncClient` for HTTP POST (sending JSON-RPC) and SSE stream reading (receiving responses). Background task reads SSE events and routes them to pending request futures by JSON-RPC `id`.

The implementer should:
- Use `httpx.AsyncClient` for all HTTP operations
- Parse SSE lines (`data:` prefix, `event:` type, blank line = event boundary)
- Match responses to requests by `id` using a `dict[str, asyncio.Future]`
- Auto-discover `post_url` from first SSE event's `data` field if not provided
- Perform MCP `initialize` handshake on connect (same as stdio)

**Tests should mock httpx responses** — use `AsyncMock` for `httpx.AsyncClient.post()` and a mock async iterator for the SSE stream. Test:
- Connect with auto-discovered post_url
- Connect with explicit post_url
- list_tools via JSON-RPC
- call_tool via JSON-RPC
- close cleans up
- health_check returns connection status

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_transports/sse.py \
       tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_sse_transport.py
git commit -m "feat(acp): implement MCPSSETransport with SSE stream + HTTP POST"
```

---

### Task 5: MCPStreamableHTTPTransport (Full Implementation)

**Files:**
- Modify: `tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_transports/streamable_http.py`
- Test: `tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_streamable_http_transport.py`

**Context:** Single endpoint, POSTs JSON-RPC. Server responds with either `application/json` (single response) or `text/event-stream` (streaming). The transport handles both transparently.

The implementer should:
- Use `httpx.AsyncClient` for POST requests
- Check response `Content-Type` header to determine mode
- For `application/json`: parse as single JSON-RPC response
- For `text/event-stream`: parse SSE stream, collect response events
- Perform MCP `initialize` handshake on connect
- Use request id matching for concurrent requests

**Tests should mock httpx** — test both response modes:
- Single JSON response mode
- Streaming SSE response mode
- list_tools, call_tool, connect handshake, close, health_check

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_transports/streamable_http.py \
       tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_streamable_http_transport.py
git commit -m "feat(acp): implement MCPStreamableHTTPTransport with dual response modes"
```

---

### Task 6: LLMCaller ABC + LLMResponse/LLMToolCall

**Files:**
- Create: `tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_llm_caller.py`
- Test: `tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_llm_caller.py`

**Step 1: Write the failing test**

```python
# tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_llm_caller.py
"""Unit tests for LLMCaller ABC and data types."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_llm_response_defaults():
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_llm_caller import LLMResponse
    r = LLMResponse()
    assert r.text is None
    assert r.tool_calls == []


def test_llm_tool_call_fields():
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_llm_caller import LLMToolCall
    tc = LLMToolCall(id="tc1", name="search", arguments={"q": "hello"})
    assert tc.id == "tc1"
    assert tc.name == "search"


def test_llm_caller_is_abstract():
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_llm_caller import LLMCaller
    with pytest.raises(TypeError):
        LLMCaller()


@pytest.mark.asyncio
async def test_llm_caller_concrete():
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_llm_caller import LLMCaller, LLMResponse

    class FakeLLM(LLMCaller):
        async def call(self, messages, tools):
            return LLMResponse(text="Hello!")

    llm = FakeLLM()
    resp = await llm.call([{"role": "user", "content": "hi"}], [])
    assert resp.text == "Hello!"


def test_mcp_tools_to_openai_format():
    """MCP tool schemas should convert to OpenAI function tool format."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_llm_caller import mcp_tools_to_openai_format

    mcp_tools = [
        {"name": "search", "description": "Search docs", "inputSchema": {"type": "object", "properties": {"q": {"type": "string"}}}},
    ]
    openai_tools = mcp_tools_to_openai_format(mcp_tools)
    assert len(openai_tools) == 1
    assert openai_tools[0]["type"] == "function"
    assert openai_tools[0]["function"]["name"] == "search"
    assert openai_tools[0]["function"]["parameters"]["type"] == "object"
```

**Step 3: Write implementation**

```python
# tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_llm_caller.py
"""LLMCaller abstraction for the MCP adapter's LLM-driven orchestration."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMToolCall:
    """A tool call requested by the LLM."""
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    """Response from an LLM call."""
    text: str | None = None
    tool_calls: list[LLMToolCall] = field(default_factory=list)


class LLMCaller(ABC):
    """Abstract interface for calling an LLM with tool definitions."""

    @abstractmethod
    async def call(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        """Send messages + tool definitions to LLM, return response."""


def mcp_tools_to_openai_format(mcp_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert MCP tool definitions to OpenAI function-calling format."""
    result = []
    for tool in mcp_tools:
        result.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("inputSchema", {"type": "object"}),
            },
        })
    return result
```

**Step 4: Run test, Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_llm_caller.py \
       tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_llm_caller.py
git commit -m "feat(acp): add LLMCaller ABC, LLMResponse, and mcp_tools_to_openai_format"
```

---

### Task 7: AgentDrivenRunner

**Files:**
- Create: `tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_runners.py`
- Test: `tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_runners_agent.py`

**Context:** AgentDrivenRunner calls the agent's entry tool, translates the response to events.

- Simple mode: text content → single COMPLETION event
- Structured mode: parse steps array → multiple events
- Receives: transport, event_callback, session_id, cancel_event, config (entry_tool, structured_response)

**Tests (mock transport):**
- test_agent_driven_simple_text_completion — transport returns text, verify COMPLETION event
- test_agent_driven_structured_steps — transport returns steps array, verify multiple events
- test_agent_driven_tool_error — transport returns error, verify ERROR event
- test_agent_driven_cancel — cancel_event set before run, verify early exit

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_runners.py \
       tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_runners_agent.py
git commit -m "feat(acp): add AgentDrivenRunner for MCP agent_driven orchestration"
```

---

### Task 8: LLMDrivenRunner

**Files:**
- Modify: `tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_runners.py` (add LLMDrivenRunner)
- Test: `tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_runners_llm.py`

**Context:** ReAct loop: LLM decides tools → ToolGate approves → transport executes → feed result back to LLM → repeat. Uses LLMCaller and ToolGate abstractions.

**Tests (mock transport + mock LLMCaller + mock ToolGate):**
- test_llm_driven_single_turn — LLM returns text immediately, verify COMPLETION
- test_llm_driven_multi_turn — LLM requests 2 tool calls then returns text, verify TOOL_CALL + TOOL_RESULT + COMPLETION events in order
- test_llm_driven_max_iterations — LLM keeps requesting tools, hits max_iterations, verify COMPLETION with stop_reason
- test_llm_driven_cancel — cancel_event set mid-loop, verify early termination
- test_llm_driven_governance_denial — ToolGate denies tool, verify error fed back to LLM and TOOL_RESULT with is_error

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_runners.py \
       tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_runners_llm.py
git commit -m "feat(acp): add LLMDrivenRunner for MCP llm_driven orchestration"
```

---

### Task 9: MCPAdapter (Wires Everything Together)

**Files:**
- Create: `tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_adapter.py`
- Test: `tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_adapter.py`

**Context:** MCPAdapter implements ProtocolAdapter. On `connect()`, creates transport, connects, discovers tools, emits lifecycle events. On `send_prompt()`, creates runner, starts heartbeat, delegates. On `cancel()`, sets cancel event. On `disconnect()`, closes transport.

**Key implementation details:**
- `protocol_config` expected keys: `mcp_transport`, `mcp_orchestration`, `mcp_entry_tool`, `mcp_structured_response`, `mcp_max_iterations`, `mcp_refresh_tools`, `tool_gate`, plus transport-specific keys
- Heartbeat: background `asyncio.Task` emitting `heartbeat` every 15s during `send_prompt()`
- `is_connected`: checks `self._connected and self._transport and self._transport.is_connected`

**Tests (mock transport, mock runners):**
- test_mcp_adapter_protocol_name
- test_mcp_adapter_not_connected_initially
- test_mcp_adapter_connect_lifecycle — connect → verify transport.connect + list_tools + lifecycle events
- test_mcp_adapter_disconnect — verify transport.close + lifecycle event
- test_mcp_adapter_send_prompt_agent_driven — verify AgentDrivenRunner created and called
- test_mcp_adapter_send_prompt_llm_driven — verify LLMDrivenRunner created and called
- test_mcp_adapter_cancel — verify cancel_event set
- test_mcp_adapter_is_connected_delegates_to_transport
- test_mcp_adapter_tool_refresh — verify list_tools called before send_prompt when enabled

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Agent_Client_Protocol/adapters/mcp_adapter.py \
       tldw_Server_API/tests/Agent_Client_Protocol/test_mcp_adapter.py
git commit -m "feat(acp): add MCPAdapter implementing ProtocolAdapter for MCP agents"
```

---

### Task 10: Agent Registry Extension (7 New Fields)

**Files:**
- Modify: `tldw_Server_API/app/core/Agent_Client_Protocol/agent_registry.py`
- Test: `tldw_Server_API/tests/Agent_Client_Protocol/test_registry_mcp_fields.py`

**Step 1: Write the failing test**

```python
# tldw_Server_API/tests/Agent_Client_Protocol/test_registry_mcp_fields.py
"""Tests for MCP-specific AgentRegistryEntry fields."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_registry_mcp_fields_defaults():
    from tldw_Server_API.app.core.Agent_Client_Protocol.agent_registry import AgentRegistryEntry

    entry = AgentRegistryEntry(type="test", name="Test")
    assert entry.mcp_orchestration == "agent_driven"
    assert entry.mcp_entry_tool == "execute"
    assert entry.mcp_structured_response is False
    assert entry.mcp_llm_provider is None
    assert entry.mcp_llm_model is None
    assert entry.mcp_max_iterations == 20
    assert entry.mcp_refresh_tools is False


def test_registry_mcp_llm_driven_config():
    from tldw_Server_API.app.core.Agent_Client_Protocol.agent_registry import AgentRegistryEntry

    entry = AgentRegistryEntry(
        type="toolbox",
        name="MCP Toolbox",
        protocol="mcp",
        mcp_orchestration="llm_driven",
        mcp_llm_provider="anthropic",
        mcp_llm_model="claude-sonnet-4-5-20250514",
        mcp_max_iterations=10,
    )
    assert entry.mcp_orchestration == "llm_driven"
    assert entry.mcp_llm_provider == "anthropic"
    assert entry.mcp_max_iterations == 10
```

**Step 3: Add fields to AgentRegistryEntry**

Add after the existing Phase A fields:

```python
    # MCP orchestration fields (Phase B)
    mcp_orchestration: Literal["agent_driven", "llm_driven"] = "agent_driven"
    mcp_entry_tool: str = "execute"
    mcp_structured_response: bool = False
    mcp_llm_provider: str | None = None
    mcp_llm_model: str | None = None
    mcp_max_iterations: int = 20
    mcp_refresh_tools: bool = False
```

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Agent_Client_Protocol/agent_registry.py \
       tldw_Server_API/tests/Agent_Client_Protocol/test_registry_mcp_fields.py
git commit -m "feat(acp): add MCP orchestration fields to AgentRegistryEntry"
```

---

### Task 11: GovernanceToolGate Concrete Implementation

**Files:**
- Modify: `tldw_Server_API/app/core/Agent_Client_Protocol/governance_filter.py`
- Test: `tldw_Server_API/tests/Agent_Client_Protocol/test_governance_tool_gate.py`

**Context:** `GovernanceToolGate` is a concrete `ToolGate` that interacts with `GovernanceFilter`. When `request_approval()` is called:
1. It creates an `AgentEvent(TOOL_CALL)` and passes it to `GovernanceFilter.process()`
2. If auto-approved (GovernanceFilter publishes tool_call directly) → return `ToolGateResult(approved=True)`
3. If held (GovernanceFilter publishes permission_request) → wait on a `Future`
4. When `GovernanceFilter.on_permission_response()` is called → resolve the `Future`

**Implementation approach:** Add a `register_tool_gate_callback` to `GovernanceFilter` so that when it holds a tool call, the `GovernanceToolGate` gets notified of the decision.

**Tests:**
- test_governance_tool_gate_auto_approved — tool with auto tier → returns approved immediately
- test_governance_tool_gate_held_then_approved — tool with individual tier → blocks, then approved via on_permission_response → returns approved
- test_governance_tool_gate_held_then_denied — same but denied → returns denied with reason

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Agent_Client_Protocol/governance_filter.py \
       tldw_Server_API/tests/Agent_Client_Protocol/test_governance_tool_gate.py
git commit -m "feat(acp): add GovernanceToolGate concrete ToolGate implementation"
```

---

### Task 12: Update Exports + Verify All Tests Pass

**Files:**
- Modify: `tldw_Server_API/app/core/Agent_Client_Protocol/adapters/__init__.py` — add MCPAdapter export

**Step 1: Update exports**

Add to `adapters/__init__.py`:
```python
from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_adapter import MCPAdapter
```

And add `"MCPAdapter"` to `__all__`.

**Step 2: Run full ACP test suite**

Run: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/ -v --timeout=120`
Expected: All tests PASS (Phase A + Phase B)

**Step 3: Commit**

```bash
git add tldw_Server_API/app/core/Agent_Client_Protocol/adapters/__init__.py
git commit -m "feat(acp): export MCPAdapter from adapters package"
```

---

## File Map

| New File | Purpose |
|----------|---------|
| `tool_gate.py` | ToolGate ABC + ToolGateResult |
| `adapters/mcp_transport.py` | MCPTransport ABC + create_transport() |
| `adapters/mcp_transports/__init__.py` | Package exports |
| `adapters/mcp_transports/stdio.py` | MCPStdioTransport |
| `adapters/mcp_transports/sse.py` | MCPSSETransport |
| `adapters/mcp_transports/streamable_http.py` | MCPStreamableHTTPTransport |
| `adapters/mcp_llm_caller.py` | LLMCaller ABC + LLMResponse + mcp_tools_to_openai_format |
| `adapters/mcp_runners.py` | AgentDrivenRunner + LLMDrivenRunner |
| `adapters/mcp_adapter.py` | MCPAdapter implementing ProtocolAdapter |

| Modified File | Change |
|---------------|--------|
| `agent_registry.py` | 7 new MCP fields |
| `governance_filter.py` | GovernanceToolGate + register_tool_gate_callback |
| `adapters/__init__.py` | Export MCPAdapter |
