# ACP Agent Workspace Harness Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a multi-protocol agent harness (stdio/MCP/OpenAI tool-use) with event bus architecture, accessible from WebUI/extension via ACP.

**Architecture:** Protocol adapters translate agent wire formats into a uniform `AgentEvent` stream. A `GovernanceFilter` pipeline stage gates tool execution. A `SessionEventBus` fans events out to consumers (WebSocket broadcaster, audit logger, metrics, orchestrator). The existing Sandbox module handles container/VM isolation.

**Tech Stack:** Python 3.11+, FastAPI, asyncio, Pydantic, pytest, SQLite (ACP_Audit_DB), existing ACP + Sandbox modules.

**Design Doc:** `Docs/Plans/2026-03-16-acp-agent-workspace-harness-design.md`

---

## Phase A: AgentEvent Schema + ProtocolAdapter Interface + StdioAdapter

Goal: Introduce the new abstractions without breaking any existing behavior. The `StdioAdapter` wraps the existing `ACPStdioClient`, all 133 ACP tests continue to pass.

---

### Task 1: AgentEvent Schema and EventKind Enum

**Files:**
- Create: `tldw_Server_API/app/core/Agent_Client_Protocol/events.py`
- Test: `tldw_Server_API/tests/Agent_Client_Protocol/test_agent_events.py`

**Step 1: Write the failing test**

```python
# tldw_Server_API/tests/Agent_Client_Protocol/test_agent_events.py
"""Unit tests for AgentEvent schema."""
from __future__ import annotations

import pytest
import json
from datetime import datetime, timezone

pytestmark = pytest.mark.unit


def test_agent_event_kind_enum_has_all_kinds():
    from tldw_Server_API.app.core.Agent_Client_Protocol.events import AgentEventKind

    expected = {
        "thinking", "tool_call", "tool_result", "file_change",
        "terminal_output", "permission_request", "permission_response",
        "completion", "error", "status_change", "token_usage",
        "heartbeat", "lifecycle",
    }
    assert {k.value for k in AgentEventKind} == expected


def test_agent_event_creation_minimal():
    from tldw_Server_API.app.core.Agent_Client_Protocol.events import AgentEvent, AgentEventKind

    ev = AgentEvent(
        session_id="sess-1",
        kind=AgentEventKind.COMPLETION,
        payload={"text": "Hello", "stop_reason": "end_turn"},
    )
    assert ev.session_id == "sess-1"
    assert ev.kind == AgentEventKind.COMPLETION
    assert ev.sequence == 0  # unassigned
    assert ev.payload["text"] == "Hello"
    assert isinstance(ev.timestamp, datetime)
    assert ev.metadata == {}


def test_agent_event_to_dict_roundtrip():
    from tldw_Server_API.app.core.Agent_Client_Protocol.events import AgentEvent, AgentEventKind

    ev = AgentEvent(
        session_id="sess-2",
        kind=AgentEventKind.TOOL_CALL,
        payload={"tool_id": "t1", "tool_name": "bash", "arguments": {"cmd": "ls"}, "permission_tier": "individual"},
        metadata={"adapter": "stdio"},
    )
    d = ev.to_dict()
    assert d["kind"] == "tool_call"
    assert d["session_id"] == "sess-2"
    assert d["payload"]["tool_name"] == "bash"
    # Verify JSON-serializable
    json.dumps(d)


def test_agent_event_all_payload_shapes():
    """Verify every event kind can be instantiated with its documented payload."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.events import AgentEvent, AgentEventKind

    payloads = {
        AgentEventKind.THINKING: {"text": "hmm", "is_partial": False},
        AgentEventKind.TOOL_CALL: {"tool_id": "t1", "tool_name": "read", "arguments": {}, "permission_tier": "auto"},
        AgentEventKind.TOOL_RESULT: {"tool_id": "t1", "tool_name": "read", "output": "data", "is_error": False, "duration_ms": 42},
        AgentEventKind.FILE_CHANGE: {"path": "/a.txt", "action": "create", "diff": None, "content": "hi"},
        AgentEventKind.TERMINAL_OUTPUT: {"command": "ls", "output": "file.txt", "exit_code": 0, "is_partial": False},
        AgentEventKind.PERMISSION_REQUEST: {"request_id": "r1", "tool_name": "bash", "arguments": {}, "tier": "individual", "timeout_sec": 300},
        AgentEventKind.PERMISSION_RESPONSE: {"request_id": "r1", "decision": "approve", "reason": None},
        AgentEventKind.COMPLETION: {"text": "done", "stop_reason": "end_turn"},
        AgentEventKind.ERROR: {"code": "adapter_disconnect", "message": "lost", "recoverable": True},
        AgentEventKind.STATUS_CHANGE: {"from_status": "idle", "to_status": "working"},
        AgentEventKind.TOKEN_USAGE: {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        AgentEventKind.HEARTBEAT: {"elapsed_sec": 15, "state": "thinking"},
        AgentEventKind.LIFECYCLE: {"event": "agent_started", "exit_code": None},
    }
    for kind, payload in payloads.items():
        ev = AgentEvent(session_id="s", kind=kind, payload=payload)
        d = ev.to_dict()
        json.dumps(d)  # must be serializable
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_agent_events.py -v`
Expected: FAIL — `ModuleNotFoundError` for `events`

**Step 3: Write minimal implementation**

```python
# tldw_Server_API/app/core/Agent_Client_Protocol/events.py
"""AgentEvent schema — the core contract for the agent workspace harness."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class AgentEventKind(str, Enum):
    """All event types in the agent event stream."""

    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    FILE_CHANGE = "file_change"
    TERMINAL_OUTPUT = "terminal_output"
    PERMISSION_REQUEST = "permission_request"
    PERMISSION_RESPONSE = "permission_response"
    COMPLETION = "completion"
    ERROR = "error"
    STATUS_CHANGE = "status_change"
    TOKEN_USAGE = "token_usage"
    HEARTBEAT = "heartbeat"
    LIFECYCLE = "lifecycle"


@dataclass
class AgentEvent:
    """Single event in an agent session's event stream."""

    session_id: str
    kind: AgentEventKind
    payload: dict[str, Any]
    sequence: int = 0  # assigned by SessionEventBus
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable dict representation."""
        return {
            "session_id": self.session_id,
            "sequence": self.sequence,
            "timestamp": self.timestamp.isoformat(),
            "kind": self.kind.value,
            "payload": self.payload,
            "metadata": self.metadata,
        }
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_agent_events.py -v`
Expected: 4 PASSED

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Agent_Client_Protocol/events.py tldw_Server_API/tests/Agent_Client_Protocol/test_agent_events.py
git commit -m "feat(acp): add AgentEvent schema and AgentEventKind enum"
```

---

### Task 2: ProtocolAdapter ABC + AdapterConfig + AdapterFactory

**Files:**
- Create: `tldw_Server_API/app/core/Agent_Client_Protocol/adapters/__init__.py`
- Create: `tldw_Server_API/app/core/Agent_Client_Protocol/adapters/base.py`
- Create: `tldw_Server_API/app/core/Agent_Client_Protocol/adapters/factory.py`
- Test: `tldw_Server_API/tests/Agent_Client_Protocol/test_adapter_base.py`

**Step 1: Write the failing test**

```python
# tldw_Server_API/tests/Agent_Client_Protocol/test_adapter_base.py
"""Unit tests for ProtocolAdapter ABC and AdapterFactory."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_protocol_adapter_is_abstract():
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.base import ProtocolAdapter

    with pytest.raises(TypeError, match="abstract"):
        ProtocolAdapter()


def test_adapter_config_creation():
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.base import AdapterConfig

    async def noop(ev):
        pass

    cfg = AdapterConfig(event_callback=noop, session_id="s1", protocol_config={"key": "val"})
    assert cfg.session_id == "s1"
    assert cfg.protocol_config["key"] == "val"


def test_adapter_factory_register_and_create():
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.factory import AdapterFactory
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.base import ProtocolAdapter, AdapterConfig

    class FakeAdapter(ProtocolAdapter):
        protocol_name = "fake"

        async def connect(self, config: AdapterConfig) -> None: pass
        async def disconnect(self) -> None: pass
        async def send_prompt(self, messages, options=None) -> None: pass
        async def send_tool_result(self, tool_id, result, is_error) -> None: pass
        async def cancel(self) -> None: pass

        @property
        def is_connected(self) -> bool: return False

        @property
        def supports_streaming(self) -> bool: return True

    factory = AdapterFactory()
    factory.register("fake", FakeAdapter)
    adapter = factory.create("fake")
    assert isinstance(adapter, FakeAdapter)
    assert adapter.protocol_name == "fake"


def test_adapter_factory_unknown_protocol_raises():
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.factory import AdapterFactory

    factory = AdapterFactory()
    with pytest.raises(ValueError, match="Unknown protocol"):
        factory.create("nonexistent")
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_adapter_base.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# tldw_Server_API/app/core/Agent_Client_Protocol/adapters/__init__.py
"""Protocol adapter subsystem for multi-protocol agent support."""
from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.base import (
    AdapterConfig,
    PromptOptions,
    ProtocolAdapter,
)
from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.factory import AdapterFactory

__all__ = ["AdapterConfig", "AdapterFactory", "PromptOptions", "ProtocolAdapter"]
```

```python
# tldw_Server_API/app/core/Agent_Client_Protocol/adapters/base.py
"""ProtocolAdapter ABC and AdapterConfig."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from tldw_Server_API.app.core.Agent_Client_Protocol.events import AgentEvent


@dataclass
class PromptOptions:
    """Options for send_prompt()."""
    max_tokens: int | None = None
    timeout_sec: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class AdapterConfig:
    """Configuration passed to ProtocolAdapter.connect()."""
    event_callback: Callable[[AgentEvent], Awaitable[None]]
    session_id: str
    protocol_config: dict[str, Any] = field(default_factory=dict)


class ProtocolAdapter(ABC):
    """Translates between an agent's native protocol and AgentEvent stream."""

    protocol_name: str  # set by subclass

    @abstractmethod
    async def connect(self, config: AdapterConfig) -> None:
        """Establish connection to the agent process/endpoint."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Gracefully close the connection."""

    @abstractmethod
    async def send_prompt(self, messages: list[dict[str, Any]], options: PromptOptions | None = None) -> None:
        """Send a user prompt. Events flow back via event_callback.

        This method is async and may run for an extended period — the agent's
        full turn. Events stream via event_callback throughout execution.
        Returns when the agent's turn is complete or on unrecoverable error.
        """

    @abstractmethod
    async def send_tool_result(self, tool_id: str, result: str, is_error: bool) -> None:
        """Return a tool execution result to the agent."""

    @abstractmethod
    async def cancel(self) -> None:
        """Cancel the current in-flight request."""

    @property
    @abstractmethod
    def is_connected(self) -> bool: ...

    @property
    @abstractmethod
    def supports_streaming(self) -> bool: ...
```

```python
# tldw_Server_API/app/core/Agent_Client_Protocol/adapters/factory.py
"""AdapterFactory — creates the right adapter for a given protocol."""
from __future__ import annotations

from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.base import ProtocolAdapter


class AdapterFactory:
    """Creates ProtocolAdapter instances by protocol name."""

    def __init__(self) -> None:
        self._registry: dict[str, type[ProtocolAdapter]] = {}

    def register(self, protocol: str, adapter_cls: type[ProtocolAdapter]) -> None:
        """Register an adapter class for a protocol name."""
        self._registry[protocol] = adapter_cls

    def create(self, protocol: str) -> ProtocolAdapter:
        """Instantiate an adapter for the given protocol."""
        cls = self._registry.get(protocol)
        if cls is None:
            raise ValueError(f"Unknown protocol: {protocol!r}")
        return cls()

    def available_protocols(self) -> list[str]:
        """Return registered protocol names."""
        return list(self._registry.keys())
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_adapter_base.py -v`
Expected: 4 PASSED

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Agent_Client_Protocol/adapters/
git add tldw_Server_API/tests/Agent_Client_Protocol/test_adapter_base.py
git commit -m "feat(acp): add ProtocolAdapter ABC, AdapterConfig, and AdapterFactory"
```

---

### Task 3: StdioAdapter — Wraps Existing ACPStdioClient

**Files:**
- Create: `tldw_Server_API/app/core/Agent_Client_Protocol/adapters/stdio_adapter.py`
- Test: `tldw_Server_API/tests/Agent_Client_Protocol/test_stdio_adapter.py`

**Context:** The existing `ACPStdioClient` (in `stdio_client.py`) uses JSON-RPC 2.0 over stdin/stdout. Key methods: `start()`, `close()`, `call(method, params)`, `notify(method, params)`, `set_request_handler()`, `set_notification_handler()`. It spawns a subprocess and reads/writes JSON frames.

The `StdioAdapter` wraps this client, translating JSON-RPC messages into `AgentEvent`s. The existing `runner_client.py` receives JSON-RPC notifications like `{"method": "update", "params": {"type": "tool_use", ...}}` and routes them. The adapter does the same translation.

**Step 1: Write the failing test**

```python
# tldw_Server_API/tests/Agent_Client_Protocol/test_stdio_adapter.py
"""Unit tests for StdioAdapter."""
from __future__ import annotations

import asyncio
import pytest

pytestmark = pytest.mark.unit


@pytest.fixture
def collected_events():
    return []


@pytest.fixture
def event_callback(collected_events):
    async def _cb(event):
        collected_events.append(event)
    return _cb


@pytest.mark.asyncio
async def test_stdio_adapter_protocol_name():
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.stdio_adapter import StdioAdapter
    adapter = StdioAdapter()
    assert adapter.protocol_name == "stdio"


@pytest.mark.asyncio
async def test_stdio_adapter_not_connected_initially():
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.stdio_adapter import StdioAdapter
    adapter = StdioAdapter()
    assert adapter.is_connected is False


@pytest.mark.asyncio
async def test_stdio_adapter_supports_streaming():
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.stdio_adapter import StdioAdapter
    adapter = StdioAdapter()
    assert adapter.supports_streaming is True


@pytest.mark.asyncio
async def test_stdio_adapter_translates_completion_notification(event_callback, collected_events):
    """Verify that a JSON-RPC notification with method='result' becomes a completion AgentEvent."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.stdio_adapter import StdioAdapter
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.base import AdapterConfig
    from tldw_Server_API.app.core.Agent_Client_Protocol.events import AgentEventKind
    from unittest.mock import AsyncMock, MagicMock

    mock_client = AsyncMock()
    mock_client.is_running = True

    adapter = StdioAdapter()
    config = AdapterConfig(
        event_callback=event_callback,
        session_id="test-sess",
        protocol_config={"client": mock_client},
    )
    await adapter.connect(config)
    assert adapter.is_connected is True

    # Simulate the notification handler being called with a result notification
    from tldw_Server_API.app.core.Agent_Client_Protocol.stdio_client import ACPMessage
    notification = ACPMessage(
        jsonrpc="2.0",
        method="result",
        params={"type": "text", "text": "Hello world", "stop_reason": "end_turn"},
    )
    await adapter._handle_notification(notification)

    assert len(collected_events) == 1
    assert collected_events[0].kind == AgentEventKind.COMPLETION
    assert collected_events[0].payload["text"] == "Hello world"


@pytest.mark.asyncio
async def test_stdio_adapter_translates_tool_use_notification(event_callback, collected_events):
    """Verify tool_use notification becomes tool_call AgentEvent."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.stdio_adapter import StdioAdapter
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.base import AdapterConfig
    from tldw_Server_API.app.core.Agent_Client_Protocol.events import AgentEventKind
    from tldw_Server_API.app.core.Agent_Client_Protocol.stdio_client import ACPMessage
    from unittest.mock import AsyncMock

    mock_client = AsyncMock()
    mock_client.is_running = True

    adapter = StdioAdapter()
    config = AdapterConfig(
        event_callback=event_callback,
        session_id="test-sess",
        protocol_config={"client": mock_client},
    )
    await adapter.connect(config)

    notification = ACPMessage(
        jsonrpc="2.0",
        method="update",
        params={"type": "tool_use", "tool_id": "t1", "tool_name": "bash", "arguments": {"cmd": "ls"}},
    )
    await adapter._handle_notification(notification)

    assert len(collected_events) == 1
    assert collected_events[0].kind == AgentEventKind.TOOL_CALL
    assert collected_events[0].payload["tool_name"] == "bash"


@pytest.mark.asyncio
async def test_stdio_adapter_disconnect(event_callback):
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.stdio_adapter import StdioAdapter
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.base import AdapterConfig
    from unittest.mock import AsyncMock

    mock_client = AsyncMock()
    mock_client.is_running = True

    adapter = StdioAdapter()
    config = AdapterConfig(
        event_callback=event_callback,
        session_id="test-sess",
        protocol_config={"client": mock_client},
    )
    await adapter.connect(config)
    assert adapter.is_connected is True

    await adapter.disconnect()
    mock_client.close.assert_awaited_once()
    assert adapter.is_connected is False
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_stdio_adapter.py -v`
Expected: FAIL — `ModuleNotFoundError` for `stdio_adapter`

**Step 3: Write minimal implementation**

```python
# tldw_Server_API/app/core/Agent_Client_Protocol/adapters/stdio_adapter.py
"""StdioAdapter — wraps ACPStdioClient to produce AgentEvent stream."""
from __future__ import annotations

from typing import Any

from loguru import logger

from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.base import (
    AdapterConfig,
    PromptOptions,
    ProtocolAdapter,
)
from tldw_Server_API.app.core.Agent_Client_Protocol.events import AgentEvent, AgentEventKind
from tldw_Server_API.app.core.Agent_Client_Protocol.permission_tiers import determine_permission_tier
from tldw_Server_API.app.core.Agent_Client_Protocol.stdio_client import ACPMessage


class StdioAdapter(ProtocolAdapter):
    """Wraps ACPStdioClient, translating JSON-RPC messages to AgentEvents."""

    protocol_name = "stdio"

    def __init__(self) -> None:
        self._client: Any | None = None
        self._config: AdapterConfig | None = None
        self._connected = False

    async def connect(self, config: AdapterConfig) -> None:
        self._config = config
        self._client = config.protocol_config.get("client")
        if self._client is None:
            raise ValueError("StdioAdapter requires 'client' in protocol_config")
        self._client.set_notification_handler(self._handle_notification)
        self._connected = True

    async def disconnect(self) -> None:
        if self._client is not None:
            await self._client.close()
        self._connected = False

    async def send_prompt(self, messages: list[dict[str, Any]], options: PromptOptions | None = None) -> None:
        if self._client is None:
            raise RuntimeError("Not connected")
        await self._client.call("prompt", {"messages": messages})

    async def send_tool_result(self, tool_id: str, result: str, is_error: bool) -> None:
        if self._client is None:
            raise RuntimeError("Not connected")
        await self._client.call("tool_result", {
            "tool_id": tool_id,
            "result": result,
            "is_error": is_error,
        })

    async def cancel(self) -> None:
        if self._client is None:
            raise RuntimeError("Not connected")
        await self._client.notify("cancel", {})

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def supports_streaming(self) -> bool:
        return True

    # --- Internal notification translation ---

    async def _handle_notification(self, msg: ACPMessage) -> None:
        """Translate JSON-RPC notifications from the agent into AgentEvents."""
        if self._config is None:
            return

        params = msg.params or {}
        method = msg.method or ""
        event: AgentEvent | None = None

        if method == "result":
            event = self._translate_result(params)
        elif method == "update":
            event = self._translate_update(params)
        elif method == "error":
            event = AgentEvent(
                session_id=self._config.session_id,
                kind=AgentEventKind.ERROR,
                payload={
                    "code": params.get("code", "agent_error"),
                    "message": params.get("message", str(params)),
                    "recoverable": params.get("recoverable", False),
                },
            )
        else:
            logger.debug(f"StdioAdapter: ignoring unknown notification method={method}")
            return

        if event is not None:
            await self._config.event_callback(event)

    def _translate_result(self, params: dict[str, Any]) -> AgentEvent:
        """Translate a 'result' notification into a completion or tool_result event."""
        assert self._config is not None
        result_type = params.get("type", "text")

        if result_type == "tool_result":
            return AgentEvent(
                session_id=self._config.session_id,
                kind=AgentEventKind.TOOL_RESULT,
                payload={
                    "tool_id": params.get("tool_id", ""),
                    "tool_name": params.get("tool_name", ""),
                    "output": params.get("output", ""),
                    "is_error": params.get("is_error", False),
                    "duration_ms": params.get("duration_ms", 0),
                },
            )
        # Default: completion
        return AgentEvent(
            session_id=self._config.session_id,
            kind=AgentEventKind.COMPLETION,
            payload={
                "text": params.get("text", ""),
                "stop_reason": params.get("stop_reason", "end_turn"),
            },
        )

    def _translate_update(self, params: dict[str, Any]) -> AgentEvent | None:
        """Translate an 'update' notification into the appropriate AgentEvent."""
        assert self._config is not None
        update_type = params.get("type", "")

        if update_type == "tool_use":
            tool_name = params.get("tool_name", "")
            return AgentEvent(
                session_id=self._config.session_id,
                kind=AgentEventKind.TOOL_CALL,
                payload={
                    "tool_id": params.get("tool_id", ""),
                    "tool_name": tool_name,
                    "arguments": params.get("arguments", {}),
                    "permission_tier": determine_permission_tier(tool_name),
                },
            )
        elif update_type == "tool_result":
            return AgentEvent(
                session_id=self._config.session_id,
                kind=AgentEventKind.TOOL_RESULT,
                payload={
                    "tool_id": params.get("tool_id", ""),
                    "tool_name": params.get("tool_name", ""),
                    "output": params.get("output", ""),
                    "is_error": params.get("is_error", False),
                    "duration_ms": params.get("duration_ms", 0),
                },
            )
        elif update_type == "thinking":
            return AgentEvent(
                session_id=self._config.session_id,
                kind=AgentEventKind.THINKING,
                payload={
                    "text": params.get("text", ""),
                    "is_partial": params.get("is_partial", True),
                },
            )
        elif update_type == "permission_request":
            return AgentEvent(
                session_id=self._config.session_id,
                kind=AgentEventKind.PERMISSION_REQUEST,
                payload={
                    "request_id": params.get("request_id", ""),
                    "tool_name": params.get("tool_name", ""),
                    "arguments": params.get("arguments", {}),
                    "tier": params.get("tier", "batch"),
                    "timeout_sec": params.get("timeout_sec", 300),
                },
            )
        else:
            logger.debug(f"StdioAdapter: ignoring unknown update type={update_type}")
            return None
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_stdio_adapter.py -v`
Expected: 6 PASSED

**Step 5: Register StdioAdapter in factory and update __init__.py**

Add to `adapters/__init__.py`:
```python
from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.stdio_adapter import StdioAdapter
```

**Step 6: Commit**

```bash
git add tldw_Server_API/app/core/Agent_Client_Protocol/adapters/stdio_adapter.py
git add tldw_Server_API/tests/Agent_Client_Protocol/test_stdio_adapter.py
git add tldw_Server_API/app/core/Agent_Client_Protocol/adapters/__init__.py
git commit -m "feat(acp): add StdioAdapter wrapping ACPStdioClient"
```

---

### Task 4: SessionEventBus

**Files:**
- Create: `tldw_Server_API/app/core/Agent_Client_Protocol/event_bus.py`
- Test: `tldw_Server_API/tests/Agent_Client_Protocol/test_event_bus.py`

**Step 1: Write the failing test**

```python
# tldw_Server_API/tests/Agent_Client_Protocol/test_event_bus.py
"""Unit tests for SessionEventBus."""
from __future__ import annotations

import asyncio
import pytest

pytestmark = pytest.mark.unit


def _make_event(session_id="s1", kind_str="completion"):
    from tldw_Server_API.app.core.Agent_Client_Protocol.events import AgentEvent, AgentEventKind
    return AgentEvent(
        session_id=session_id,
        kind=AgentEventKind(kind_str),
        payload={"text": "test"},
    )


@pytest.mark.asyncio
async def test_bus_assigns_sequence_numbers():
    from tldw_Server_API.app.core.Agent_Client_Protocol.event_bus import SessionEventBus

    bus = SessionEventBus("s1")
    q = bus.subscribe("c1")

    ev1 = _make_event()
    ev2 = _make_event()
    await bus.publish(ev1)
    await bus.publish(ev2)

    r1 = q.get_nowait()
    r2 = q.get_nowait()
    assert r1.sequence == 1
    assert r2.sequence == 2


@pytest.mark.asyncio
async def test_bus_fan_out_to_multiple_subscribers():
    from tldw_Server_API.app.core.Agent_Client_Protocol.event_bus import SessionEventBus

    bus = SessionEventBus("s1")
    q1 = bus.subscribe("c1")
    q2 = bus.subscribe("c2")

    await bus.publish(_make_event())

    assert not q1.empty()
    assert not q2.empty()
    assert q1.get_nowait().sequence == q2.get_nowait().sequence == 1


@pytest.mark.asyncio
async def test_bus_unsubscribe_stops_delivery():
    from tldw_Server_API.app.core.Agent_Client_Protocol.event_bus import SessionEventBus

    bus = SessionEventBus("s1")
    q = bus.subscribe("c1")
    bus.unsubscribe("c1")

    await bus.publish(_make_event())
    assert q.empty()


@pytest.mark.asyncio
async def test_bus_snapshot_returns_history():
    from tldw_Server_API.app.core.Agent_Client_Protocol.event_bus import SessionEventBus

    bus = SessionEventBus("s1", max_buffer=100)
    for _ in range(5):
        await bus.publish(_make_event())

    snap = bus.snapshot(from_sequence=3)
    assert len(snap) == 3  # sequences 3, 4, 5
    assert snap[0].sequence == 3


@pytest.mark.asyncio
async def test_bus_snapshot_respects_buffer_limit():
    from tldw_Server_API.app.core.Agent_Client_Protocol.event_bus import SessionEventBus

    bus = SessionEventBus("s1", max_buffer=3)
    for _ in range(5):
        await bus.publish(_make_event())

    # Buffer only holds last 3 (sequences 3, 4, 5)
    snap = bus.snapshot(from_sequence=1)
    assert len(snap) == 3
    assert snap[0].sequence == 3


@pytest.mark.asyncio
async def test_bus_inject_delivers_event():
    from tldw_Server_API.app.core.Agent_Client_Protocol.event_bus import SessionEventBus

    bus = SessionEventBus("s1")
    q = bus.subscribe("c1")

    ev = _make_event(kind_str="permission_response")
    await bus.inject(ev)

    r = q.get_nowait()
    assert r.kind.value == "permission_response"
    assert r.sequence == 1  # inject also gets a sequence number


@pytest.mark.asyncio
async def test_bus_backpressure_drops_to_full_queue():
    from tldw_Server_API.app.core.Agent_Client_Protocol.event_bus import SessionEventBus

    bus = SessionEventBus("s1", subscriber_queue_size=2)
    q = bus.subscribe("c1")

    # Fill the queue
    await bus.publish(_make_event())
    await bus.publish(_make_event())
    # Third should not raise but queue is full — event dropped for this subscriber
    await bus.publish(_make_event())

    assert q.qsize() == 2  # only 2 fit
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_event_bus.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# tldw_Server_API/app/core/Agent_Client_Protocol/event_bus.py
"""SessionEventBus — per-session event fan-out with ordering guarantees."""
from __future__ import annotations

import asyncio
from collections import deque
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.Agent_Client_Protocol.events import AgentEvent


class SessionEventBus:
    """Per-session event fan-out with monotonic sequencing and bounded history."""

    def __init__(
        self,
        session_id: str,
        max_buffer: int = 10_000,
        subscriber_queue_size: int = 1_000,
    ) -> None:
        self._session_id = session_id
        self._sequence = 0
        self._subscribers: dict[str, asyncio.Queue[AgentEvent]] = {}
        self._history: deque[AgentEvent] = deque(maxlen=max_buffer)
        self._subscriber_queue_size = subscriber_queue_size

    async def publish(self, event: AgentEvent) -> None:
        """Assign sequence number and distribute to all subscribers."""
        self._sequence += 1
        event.sequence = self._sequence
        self._history.append(event)
        await self._distribute(event)

    async def inject(self, event: AgentEvent) -> None:
        """Inject an external event (e.g., permission_response). Same as publish."""
        await self.publish(event)

    def subscribe(
        self, consumer_id: str, from_sequence: int = 0
    ) -> asyncio.Queue[AgentEvent]:
        """Subscribe to events. If from_sequence > 0, replay from history."""
        q: asyncio.Queue[AgentEvent] = asyncio.Queue(
            maxsize=self._subscriber_queue_size
        )
        self._subscribers[consumer_id] = q

        if from_sequence > 0:
            for ev in self._history:
                if ev.sequence >= from_sequence:
                    try:
                        q.put_nowait(ev)
                    except asyncio.QueueFull:
                        break
        return q

    def unsubscribe(self, consumer_id: str) -> None:
        """Remove a subscriber."""
        self._subscribers.pop(consumer_id, None)

    def snapshot(self, from_sequence: int = 0) -> list[AgentEvent]:
        """Return event history from a given sequence."""
        return [ev for ev in self._history if ev.sequence >= from_sequence]

    @property
    def min_sequence(self) -> int:
        """Earliest sequence still in the buffer, or 0 if empty."""
        return self._history[0].sequence if self._history else 0

    @property
    def current_sequence(self) -> int:
        """Current (latest) sequence number."""
        return self._sequence

    async def _distribute(self, event: AgentEvent) -> None:
        """Send event to all subscriber queues. Drop on full queue."""
        for consumer_id, q in list(self._subscribers.items()):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(
                    f"SessionEventBus: queue full for consumer={consumer_id}, "
                    f"session={self._session_id}, dropping event seq={event.sequence}"
                )
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_event_bus.py -v`
Expected: 7 PASSED

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Agent_Client_Protocol/event_bus.py
git add tldw_Server_API/tests/Agent_Client_Protocol/test_event_bus.py
git commit -m "feat(acp): add SessionEventBus with sequencing, fan-out, and replay"
```

---

### Task 5: GovernanceFilter Pipeline Stage

**Files:**
- Create: `tldw_Server_API/app/core/Agent_Client_Protocol/governance_filter.py`
- Test: `tldw_Server_API/tests/Agent_Client_Protocol/test_governance_filter.py`

**Step 1: Write the failing test**

```python
# tldw_Server_API/tests/Agent_Client_Protocol/test_governance_filter.py
"""Unit tests for GovernanceFilter pipeline stage."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def _make_tool_call_event(session_id="s1", tool_name="bash"):
    from tldw_Server_API.app.core.Agent_Client_Protocol.events import AgentEvent, AgentEventKind
    return AgentEvent(
        session_id=session_id,
        kind=AgentEventKind.TOOL_CALL,
        payload={
            "tool_id": "t1",
            "tool_name": tool_name,
            "arguments": {"cmd": "ls"},
            "permission_tier": "individual",
        },
    )


def _make_thinking_event(session_id="s1"):
    from tldw_Server_API.app.core.Agent_Client_Protocol.events import AgentEvent, AgentEventKind
    return AgentEvent(
        session_id=session_id,
        kind=AgentEventKind.THINKING,
        payload={"text": "hmm", "is_partial": False},
    )


@pytest.mark.asyncio
async def test_governance_passes_non_tool_events_immediately():
    from tldw_Server_API.app.core.Agent_Client_Protocol.event_bus import SessionEventBus
    from tldw_Server_API.app.core.Agent_Client_Protocol.governance_filter import GovernanceFilter

    bus = SessionEventBus("s1")
    q = bus.subscribe("test")
    gf = GovernanceFilter(bus=bus)

    ev = _make_thinking_event()
    await gf.process(ev)

    assert not q.empty()
    assert q.get_nowait().kind.value == "thinking"


@pytest.mark.asyncio
async def test_governance_auto_tier_passes_through():
    from tldw_Server_API.app.core.Agent_Client_Protocol.event_bus import SessionEventBus
    from tldw_Server_API.app.core.Agent_Client_Protocol.governance_filter import GovernanceFilter

    bus = SessionEventBus("s1")
    q = bus.subscribe("test")
    gf = GovernanceFilter(bus=bus)

    # "read_file" matches "read" → auto tier
    ev = _make_tool_call_event(tool_name="read_file")
    await gf.process(ev)

    assert not q.empty()
    result = q.get_nowait()
    assert result.kind.value == "tool_call"


@pytest.mark.asyncio
async def test_governance_individual_tier_holds_and_emits_permission_request():
    from tldw_Server_API.app.core.Agent_Client_Protocol.event_bus import SessionEventBus
    from tldw_Server_API.app.core.Agent_Client_Protocol.governance_filter import GovernanceFilter

    bus = SessionEventBus("s1")
    q = bus.subscribe("test")
    gf = GovernanceFilter(bus=bus)

    ev = _make_tool_call_event(tool_name="bash")  # "bash" → individual
    await gf.process(ev)

    # Should emit permission_request, NOT the tool_call
    result = q.get_nowait()
    assert result.kind.value == "permission_request"
    assert result.payload["tool_name"] == "bash"
    assert q.empty()  # tool_call is held

    # Pending count
    assert gf.pending_count == 1


@pytest.mark.asyncio
async def test_governance_approve_releases_held_tool_call():
    from tldw_Server_API.app.core.Agent_Client_Protocol.event_bus import SessionEventBus
    from tldw_Server_API.app.core.Agent_Client_Protocol.governance_filter import GovernanceFilter

    bus = SessionEventBus("s1")
    q = bus.subscribe("test")
    gf = GovernanceFilter(bus=bus)

    ev = _make_tool_call_event(tool_name="bash")
    await gf.process(ev)

    perm_req = q.get_nowait()
    request_id = perm_req.payload["request_id"]

    await gf.on_permission_response(request_id, "approve")

    released = q.get_nowait()
    assert released.kind.value == "tool_call"
    assert released.payload["tool_name"] == "bash"
    assert gf.pending_count == 0


@pytest.mark.asyncio
async def test_governance_deny_emits_error_tool_result():
    from tldw_Server_API.app.core.Agent_Client_Protocol.event_bus import SessionEventBus
    from tldw_Server_API.app.core.Agent_Client_Protocol.governance_filter import GovernanceFilter

    bus = SessionEventBus("s1")
    q = bus.subscribe("test")
    gf = GovernanceFilter(bus=bus)

    ev = _make_tool_call_event(tool_name="delete_all")  # "delete" → individual
    await gf.process(ev)

    perm_req = q.get_nowait()
    request_id = perm_req.payload["request_id"]

    await gf.on_permission_response(request_id, "deny")

    denied = q.get_nowait()
    assert denied.kind.value == "tool_result"
    assert denied.payload["is_error"] is True
    assert "denied" in denied.payload["output"].lower()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_governance_filter.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# tldw_Server_API/app/core/Agent_Client_Protocol/governance_filter.py
"""GovernanceFilter — pipeline stage between adapter and bus that gates tool execution."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from loguru import logger

from tldw_Server_API.app.core.Agent_Client_Protocol.event_bus import SessionEventBus
from tldw_Server_API.app.core.Agent_Client_Protocol.events import AgentEvent, AgentEventKind
from tldw_Server_API.app.core.Agent_Client_Protocol.permission_tiers import determine_permission_tier


@dataclass
class PendingToolCall:
    """A tool_call event held pending permission approval."""

    event: AgentEvent
    tier: str
    request_id: str


class GovernanceFilter:
    """Pipeline stage between adapter and bus. NOT a bus consumer.

    Intercepts tool_call events, checks permission tier, and either:
    - Forwards immediately (auto tier)
    - Holds and emits permission_request (batch/individual tiers)
    """

    def __init__(
        self,
        bus: SessionEventBus,
        default_timeout_sec: int = 300,
    ) -> None:
        self._bus = bus
        self._pending: dict[str, PendingToolCall] = {}
        self._default_timeout_sec = default_timeout_sec

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    async def process(self, event: AgentEvent) -> None:
        """Called by adapter's event_callback. Gates tool_calls, forwards everything else."""
        if event.kind != AgentEventKind.TOOL_CALL:
            await self._bus.publish(event)
            return

        tool_name = event.payload.get("tool_name", "")
        tier = determine_permission_tier(tool_name)

        if tier == "auto":
            await self._bus.publish(event)
            return

        # Hold the tool_call and emit a permission_request
        request_id = str(uuid4())
        self._pending[request_id] = PendingToolCall(
            event=event, tier=tier, request_id=request_id,
        )

        perm_event = AgentEvent(
            session_id=event.session_id,
            kind=AgentEventKind.PERMISSION_REQUEST,
            payload={
                "request_id": request_id,
                "tool_name": tool_name,
                "arguments": event.payload.get("arguments", {}),
                "tier": tier,
                "timeout_sec": self._default_timeout_sec,
            },
        )
        await self._bus.publish(perm_event)

    async def on_permission_response(self, request_id: str, decision: str, reason: str | None = None) -> None:
        """Handle a permission decision. Releases or denies the held tool_call."""
        pending = self._pending.pop(request_id, None)
        if pending is None:
            logger.warning(f"GovernanceFilter: unknown request_id={request_id}")
            return

        if decision == "approve":
            await self._bus.publish(pending.event)
        else:
            await self._bus.publish(AgentEvent(
                session_id=pending.event.session_id,
                kind=AgentEventKind.TOOL_RESULT,
                payload={
                    "tool_id": pending.event.payload.get("tool_id", ""),
                    "tool_name": pending.event.payload.get("tool_name", ""),
                    "output": f"Permission denied: {reason or decision}",
                    "is_error": True,
                    "duration_ms": 0,
                },
            ))

    async def cancel_all_pending(self) -> None:
        """Cancel all pending permission requests (e.g., on session close)."""
        for request_id in list(self._pending.keys()):
            await self.on_permission_response(request_id, "deny", reason="session_closed")
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_governance_filter.py -v`
Expected: 5 PASSED

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Agent_Client_Protocol/governance_filter.py
git add tldw_Server_API/tests/Agent_Client_Protocol/test_governance_filter.py
git commit -m "feat(acp): add GovernanceFilter pipeline stage for tool permission gating"
```

---

### Task 6: EventConsumer ABC + WSBroadcaster Consumer

**Files:**
- Create: `tldw_Server_API/app/core/Agent_Client_Protocol/consumers/__init__.py`
- Create: `tldw_Server_API/app/core/Agent_Client_Protocol/consumers/base.py`
- Create: `tldw_Server_API/app/core/Agent_Client_Protocol/consumers/ws_broadcaster.py`
- Test: `tldw_Server_API/tests/Agent_Client_Protocol/test_ws_broadcaster.py`

**Step 1: Write the failing test**

```python
# tldw_Server_API/tests/Agent_Client_Protocol/test_ws_broadcaster.py
"""Unit tests for WSBroadcaster consumer."""
from __future__ import annotations

import asyncio
import json
import pytest

pytestmark = pytest.mark.unit


def _make_event(kind_str="completion"):
    from tldw_Server_API.app.core.Agent_Client_Protocol.events import AgentEvent, AgentEventKind
    return AgentEvent(session_id="s1", kind=AgentEventKind(kind_str), payload={"text": "test"})


@pytest.mark.asyncio
async def test_ws_broadcaster_delivers_events_full_verbosity():
    from tldw_Server_API.app.core.Agent_Client_Protocol.event_bus import SessionEventBus
    from tldw_Server_API.app.core.Agent_Client_Protocol.consumers.ws_broadcaster import WSBroadcaster

    bus = SessionEventBus("s1")
    broadcaster = WSBroadcaster(bus=bus)

    received = []
    async def mock_send(data):
        received.append(json.loads(data) if isinstance(data, str) else data)

    broadcaster.add_connection("ws1", mock_send, verbosity="full")
    await broadcaster.start()

    await bus.publish(_make_event("completion"))
    await bus.publish(_make_event("thinking"))

    await asyncio.sleep(0.05)  # let consumer loop process
    await broadcaster.stop()

    assert len(received) == 2
    assert received[0]["kind"] == "completion"
    assert received[1]["kind"] == "thinking"


@pytest.mark.asyncio
async def test_ws_broadcaster_summary_filters_thinking():
    from tldw_Server_API.app.core.Agent_Client_Protocol.event_bus import SessionEventBus
    from tldw_Server_API.app.core.Agent_Client_Protocol.consumers.ws_broadcaster import WSBroadcaster

    bus = SessionEventBus("s1")
    broadcaster = WSBroadcaster(bus=bus)

    received = []
    async def mock_send(data):
        received.append(json.loads(data) if isinstance(data, str) else data)

    broadcaster.add_connection("ws1", mock_send, verbosity="summary")
    await broadcaster.start()

    await bus.publish(_make_event("thinking"))
    await bus.publish(_make_event("completion"))
    await bus.publish(_make_event("tool_call"))

    await asyncio.sleep(0.05)
    await broadcaster.stop()

    # summary only delivers: completion, error, permission_*, status_change
    assert len(received) == 1
    assert received[0]["kind"] == "completion"


@pytest.mark.asyncio
async def test_ws_broadcaster_remove_connection():
    from tldw_Server_API.app.core.Agent_Client_Protocol.event_bus import SessionEventBus
    from tldw_Server_API.app.core.Agent_Client_Protocol.consumers.ws_broadcaster import WSBroadcaster

    bus = SessionEventBus("s1")
    broadcaster = WSBroadcaster(bus=bus)

    received = []
    async def mock_send(data):
        received.append(data)

    broadcaster.add_connection("ws1", mock_send, verbosity="full")
    broadcaster.remove_connection("ws1")
    await broadcaster.start()

    await bus.publish(_make_event("completion"))
    await asyncio.sleep(0.05)
    await broadcaster.stop()

    assert len(received) == 0


@pytest.mark.asyncio
async def test_ws_broadcaster_change_verbosity():
    from tldw_Server_API.app.core.Agent_Client_Protocol.event_bus import SessionEventBus
    from tldw_Server_API.app.core.Agent_Client_Protocol.consumers.ws_broadcaster import WSBroadcaster

    bus = SessionEventBus("s1")
    broadcaster = WSBroadcaster(bus=bus)

    received = []
    async def mock_send(data):
        received.append(json.loads(data) if isinstance(data, str) else data)

    broadcaster.add_connection("ws1", mock_send, verbosity="summary")
    broadcaster.set_verbosity("ws1", "full")
    await broadcaster.start()

    await bus.publish(_make_event("thinking"))
    await asyncio.sleep(0.05)
    await broadcaster.stop()

    # After switching to full, thinking should come through
    assert len(received) == 1
    assert received[0]["kind"] == "thinking"
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_ws_broadcaster.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# tldw_Server_API/app/core/Agent_Client_Protocol/consumers/__init__.py
"""Event bus consumers."""
from tldw_Server_API.app.core.Agent_Client_Protocol.consumers.base import EventConsumer

__all__ = ["EventConsumer"]
```

```python
# tldw_Server_API/app/core/Agent_Client_Protocol/consumers/base.py
"""EventConsumer ABC."""
from __future__ import annotations

from abc import ABC, abstractmethod

from tldw_Server_API.app.core.Agent_Client_Protocol.event_bus import SessionEventBus
from tldw_Server_API.app.core.Agent_Client_Protocol.events import AgentEvent


class EventConsumer(ABC):
    """Base class for bus consumers."""

    consumer_id: str

    @abstractmethod
    async def on_event(self, event: AgentEvent) -> None:
        """Process an event."""

    @abstractmethod
    async def start(self, bus: SessionEventBus) -> None:
        """Subscribe to bus and begin processing loop."""

    @abstractmethod
    async def stop(self) -> None:
        """Unsubscribe and clean up."""
```

```python
# tldw_Server_API/app/core/Agent_Client_Protocol/consumers/ws_broadcaster.py
"""WSBroadcaster — forwards events to WebSocket connections with verbosity filtering."""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from loguru import logger

from tldw_Server_API.app.core.Agent_Client_Protocol.consumers.base import EventConsumer
from tldw_Server_API.app.core.Agent_Client_Protocol.event_bus import SessionEventBus
from tldw_Server_API.app.core.Agent_Client_Protocol.events import AgentEvent

# Events delivered at each verbosity level
_SUMMARY_KINDS = {"completion", "error", "permission_request", "permission_response", "status_change"}
_STRUCTURED_KINDS = _SUMMARY_KINDS | {"tool_call", "tool_result", "file_change", "lifecycle"}


@dataclass
class _WSConnection:
    send: Callable[[str], Awaitable[None]]
    verbosity: str = "full"


class WSBroadcaster(EventConsumer):
    """Forwards AgentEvents to WebSocket connections with per-connection verbosity filtering."""

    consumer_id = "ws_broadcaster"

    def __init__(self, bus: SessionEventBus) -> None:
        self._bus = bus
        self._connections: dict[str, _WSConnection] = {}
        self._queue: asyncio.Queue[AgentEvent] | None = None
        self._task: asyncio.Task[None] | None = None
        self._running = False

    def add_connection(
        self,
        conn_id: str,
        send_callback: Callable[[str], Awaitable[None]],
        verbosity: str = "full",
    ) -> None:
        self._connections[conn_id] = _WSConnection(send=send_callback, verbosity=verbosity)

    def remove_connection(self, conn_id: str) -> None:
        self._connections.pop(conn_id, None)

    def set_verbosity(self, conn_id: str, verbosity: str) -> None:
        conn = self._connections.get(conn_id)
        if conn:
            conn.verbosity = verbosity

    async def start(self, bus: SessionEventBus | None = None) -> None:
        if bus is not None:
            self._bus = bus
        self._queue = self._bus.subscribe(self.consumer_id)
        self._running = True
        self._task = asyncio.create_task(self._consume_loop())

    async def stop(self) -> None:
        self._running = False
        self._bus.unsubscribe(self.consumer_id)
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def on_event(self, event: AgentEvent) -> None:
        await self._broadcast(event)

    async def _consume_loop(self) -> None:
        assert self._queue is not None
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self._broadcast(event)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

    async def _broadcast(self, event: AgentEvent) -> None:
        kind_str = event.kind.value
        data = json.dumps(event.to_dict())

        for conn_id, conn in list(self._connections.items()):
            if not self._should_deliver(kind_str, conn.verbosity):
                continue
            try:
                await conn.send(data)
            except Exception:
                logger.warning(f"WSBroadcaster: failed to send to {conn_id}, removing")
                self._connections.pop(conn_id, None)

    @staticmethod
    def _should_deliver(kind: str, verbosity: str) -> bool:
        if verbosity == "full":
            return True
        if verbosity == "summary":
            return kind in _SUMMARY_KINDS
        if verbosity == "structured":
            return kind in _STRUCTURED_KINDS
        return True  # unknown verbosity → deliver
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_ws_broadcaster.py -v`
Expected: 4 PASSED

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Agent_Client_Protocol/consumers/
git add tldw_Server_API/tests/Agent_Client_Protocol/test_ws_broadcaster.py
git commit -m "feat(acp): add EventConsumer ABC and WSBroadcaster with verbosity filtering"
```

---

### Task 7: AuditLogger + MetricsRecorder Consumers

**Files:**
- Create: `tldw_Server_API/app/core/Agent_Client_Protocol/consumers/audit_logger.py`
- Create: `tldw_Server_API/app/core/Agent_Client_Protocol/consumers/metrics_recorder.py`
- Test: `tldw_Server_API/tests/Agent_Client_Protocol/test_consumers.py`

These are simpler consumers. AuditLogger batches events and writes to the existing `ACP_Audit_DB`. MetricsRecorder updates the existing Prometheus metrics from `metrics.py`.

**Step 1: Write the failing tests**

```python
# tldw_Server_API/tests/Agent_Client_Protocol/test_consumers.py
"""Unit tests for AuditLogger and MetricsRecorder consumers."""
from __future__ import annotations

import asyncio
import pytest

pytestmark = pytest.mark.unit


def _make_event(kind_str="completion"):
    from tldw_Server_API.app.core.Agent_Client_Protocol.events import AgentEvent, AgentEventKind
    return AgentEvent(session_id="s1", kind=AgentEventKind(kind_str), payload={"text": "test"})


@pytest.mark.asyncio
async def test_audit_logger_batches_events():
    from tldw_Server_API.app.core.Agent_Client_Protocol.event_bus import SessionEventBus
    from tldw_Server_API.app.core.Agent_Client_Protocol.consumers.audit_logger import AuditLogger

    bus = SessionEventBus("s1")
    written = []

    async def mock_write_batch(events):
        written.extend(events)

    logger_consumer = AuditLogger(bus=bus, write_batch_fn=mock_write_batch, flush_interval=0.05, batch_size=3)
    await logger_consumer.start()

    # Publish 3 events to trigger batch flush
    for _ in range(3):
        await bus.publish(_make_event())

    await asyncio.sleep(0.1)
    await logger_consumer.stop()

    assert len(written) == 3


@pytest.mark.asyncio
async def test_audit_logger_flushes_on_interval():
    from tldw_Server_API.app.core.Agent_Client_Protocol.event_bus import SessionEventBus
    from tldw_Server_API.app.core.Agent_Client_Protocol.consumers.audit_logger import AuditLogger

    bus = SessionEventBus("s1")
    written = []

    async def mock_write_batch(events):
        written.extend(events)

    logger_consumer = AuditLogger(bus=bus, write_batch_fn=mock_write_batch, flush_interval=0.05, batch_size=100)
    await logger_consumer.start()

    await bus.publish(_make_event())
    # Only 1 event, batch_size=100, but flush_interval=0.05s should trigger
    await asyncio.sleep(0.15)
    await logger_consumer.stop()

    assert len(written) == 1


@pytest.mark.asyncio
async def test_metrics_recorder_counts_tool_calls():
    from tldw_Server_API.app.core.Agent_Client_Protocol.event_bus import SessionEventBus
    from tldw_Server_API.app.core.Agent_Client_Protocol.consumers.metrics_recorder import MetricsRecorder

    bus = SessionEventBus("s1")
    recorder = MetricsRecorder(bus=bus)
    await recorder.start()

    await bus.publish(_make_event("tool_call"))
    await bus.publish(_make_event("tool_call"))
    await bus.publish(_make_event("completion"))

    await asyncio.sleep(0.05)
    await recorder.stop()

    assert recorder.counters["tool_call"] == 2
    assert recorder.counters["completion"] == 1
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_consumers.py -v`
Expected: FAIL

**Step 3: Write minimal implementations**

```python
# tldw_Server_API/app/core/Agent_Client_Protocol/consumers/audit_logger.py
"""AuditLogger — persists AgentEvents to durable storage in batches."""
from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable

from loguru import logger

from tldw_Server_API.app.core.Agent_Client_Protocol.consumers.base import EventConsumer
from tldw_Server_API.app.core.Agent_Client_Protocol.event_bus import SessionEventBus
from tldw_Server_API.app.core.Agent_Client_Protocol.events import AgentEvent


class AuditLogger(EventConsumer):
    """Batches events and writes to durable storage."""

    consumer_id = "audit_logger"

    def __init__(
        self,
        bus: SessionEventBus,
        write_batch_fn: Callable[[list[AgentEvent]], Awaitable[None]],
        batch_size: int = 100,
        flush_interval: float = 5.0,
    ) -> None:
        self._bus = bus
        self._write_batch = write_batch_fn
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._buffer: list[AgentEvent] = []
        self._last_flush = time.monotonic()
        self._queue: asyncio.Queue[AgentEvent] | None = None
        self._task: asyncio.Task[None] | None = None
        self._running = False

    async def start(self, bus: SessionEventBus | None = None) -> None:
        if bus is not None:
            self._bus = bus
        self._queue = self._bus.subscribe(self.consumer_id)
        self._running = True
        self._task = asyncio.create_task(self._consume_loop())

    async def stop(self) -> None:
        self._running = False
        self._bus.unsubscribe(self.consumer_id)
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self._flush()

    async def on_event(self, event: AgentEvent) -> None:
        self._buffer.append(event)
        if len(self._buffer) >= self._batch_size:
            await self._flush()

    async def _consume_loop(self) -> None:
        assert self._queue is not None
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=self._flush_interval)
                await self.on_event(event)
            except asyncio.TimeoutError:
                if self._buffer:
                    await self._flush()
            except asyncio.CancelledError:
                break

    async def _flush(self) -> None:
        if not self._buffer:
            return
        batch = self._buffer[:]
        self._buffer.clear()
        self._last_flush = time.monotonic()
        try:
            await self._write_batch(batch)
        except Exception:
            logger.exception("AuditLogger: failed to write batch")
```

```python
# tldw_Server_API/app/core/Agent_Client_Protocol/consumers/metrics_recorder.py
"""MetricsRecorder — updates counters from AgentEvents."""
from __future__ import annotations

import asyncio
from collections import Counter

from loguru import logger

from tldw_Server_API.app.core.Agent_Client_Protocol.consumers.base import EventConsumer
from tldw_Server_API.app.core.Agent_Client_Protocol.event_bus import SessionEventBus
from tldw_Server_API.app.core.Agent_Client_Protocol.events import AgentEvent


class MetricsRecorder(EventConsumer):
    """Counts events by kind. Integrates with Prometheus via existing metrics module."""

    consumer_id = "metrics_recorder"

    def __init__(self, bus: SessionEventBus) -> None:
        self._bus = bus
        self._queue: asyncio.Queue[AgentEvent] | None = None
        self._task: asyncio.Task[None] | None = None
        self._running = False
        self.counters: Counter[str] = Counter()

    async def start(self, bus: SessionEventBus | None = None) -> None:
        if bus is not None:
            self._bus = bus
        self._queue = self._bus.subscribe(self.consumer_id)
        self._running = True
        self._task = asyncio.create_task(self._consume_loop())

    async def stop(self) -> None:
        self._running = False
        self._bus.unsubscribe(self.consumer_id)
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def on_event(self, event: AgentEvent) -> None:
        self.counters[event.kind.value] += 1

    async def _consume_loop(self) -> None:
        assert self._queue is not None
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self.on_event(event)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_consumers.py -v`
Expected: 3 PASSED

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Agent_Client_Protocol/consumers/audit_logger.py
git add tldw_Server_API/app/core/Agent_Client_Protocol/consumers/metrics_recorder.py
git add tldw_Server_API/tests/Agent_Client_Protocol/test_consumers.py
git commit -m "feat(acp): add AuditLogger and MetricsRecorder event bus consumers"
```

---

### Task 8: Agent Registry Extension — New Fields

**Files:**
- Modify: `tldw_Server_API/app/core/Agent_Client_Protocol/agent_registry.py`
- Test: `tldw_Server_API/tests/Agent_Client_Protocol/test_registry_extension.py`

**Step 1: Write the failing test**

```python
# tldw_Server_API/tests/Agent_Client_Protocol/test_registry_extension.py
"""Tests for extended AgentRegistryEntry fields."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_registry_entry_new_fields_have_defaults():
    from tldw_Server_API.app.core.Agent_Client_Protocol.agent_registry import AgentRegistryEntry

    entry = AgentRegistryEntry(type="test-agent", name="Test")
    assert entry.protocol == "stdio"
    assert entry.tool_execution_mode == "agent_side"
    assert entry.mcp_transport == "stdio"
    assert entry.api_base_url is None
    assert entry.model is None
    assert entry.tools_from == "auto"
    assert entry.sandbox == "none"
    assert entry.trust_level == "standard"


def test_registry_entry_with_openai_protocol():
    from tldw_Server_API.app.core.Agent_Client_Protocol.agent_registry import AgentRegistryEntry

    entry = AgentRegistryEntry(
        type="ollama",
        name="Ollama",
        protocol="openai_tool_use",
        tool_execution_mode="server_side",
        api_base_url="http://localhost:11434/v1",
        model="llama3.1",
        sandbox="required",
        trust_level="untrusted",
    )
    assert entry.protocol == "openai_tool_use"
    assert entry.tool_execution_mode == "server_side"
    assert entry.api_base_url == "http://localhost:11434/v1"


def test_registry_entry_from_yaml_dict_with_new_fields():
    from tldw_Server_API.app.core.Agent_Client_Protocol.agent_registry import AgentRegistryEntry

    data = {
        "type": "mcp-agent",
        "name": "MCP Agent",
        "protocol": "mcp",
        "mcp_transport": "streamable_http",
        "tool_execution_mode": "server_side",
        "command": "/usr/bin/agent",
    }
    entry = AgentRegistryEntry(**{k: v for k, v in data.items() if k in AgentRegistryEntry.__dataclass_fields__})
    assert entry.protocol == "mcp"
    assert entry.mcp_transport == "streamable_http"
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_registry_extension.py -v`
Expected: FAIL — `AgentRegistryEntry` doesn't have `protocol` field yet

**Step 3: Add new fields to `AgentRegistryEntry`**

Add the following fields to the existing `AgentRegistryEntry` dataclass in `agent_registry.py` (after the existing fields):

```python
    # Protocol adapter fields (new for agent workspace harness)
    protocol: str = "stdio"  # stdio | mcp | openai_tool_use
    tool_execution_mode: str = "agent_side"  # agent_side | server_side | hybrid
    mcp_transport: str = "stdio"  # stdio | sse | streamable_http
    api_base_url: str | None = None
    model: str | None = None
    tools_from: str = "auto"  # auto | static | none
    sandbox: str = "none"  # required | optional | none
    trust_level: str = "standard"  # untrusted | standard | trusted
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_registry_extension.py -v`
Expected: 3 PASSED

**Step 5: Verify existing tests still pass**

Run: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/ -v --timeout=60`
Expected: All existing tests PASS (new fields have defaults, backward compatible)

**Step 6: Commit**

```bash
git add tldw_Server_API/app/core/Agent_Client_Protocol/agent_registry.py
git add tldw_Server_API/tests/Agent_Client_Protocol/test_registry_extension.py
git commit -m "feat(acp): extend AgentRegistryEntry with protocol and sandbox fields"
```

---

### Task 9: ToolExecutor Interface + Default Implementation

**Files:**
- Create: `tldw_Server_API/app/core/Agent_Client_Protocol/tool_executor.py`
- Test: `tldw_Server_API/tests/Agent_Client_Protocol/test_tool_executor.py`

**Step 1: Write the failing test**

```python
# tldw_Server_API/tests/Agent_Client_Protocol/test_tool_executor.py
"""Unit tests for ToolExecutor."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_tool_executor_is_abstract():
    from tldw_Server_API.app.core.Agent_Client_Protocol.tool_executor import ToolExecutor
    with pytest.raises(TypeError):
        ToolExecutor()


@pytest.mark.asyncio
async def test_default_tool_executor_unknown_tool_returns_error():
    from tldw_Server_API.app.core.Agent_Client_Protocol.tool_executor import DefaultToolExecutor

    executor = DefaultToolExecutor()
    result = await executor.execute("nonexistent_tool", {})
    assert result.is_error is True
    assert "unknown" in result.output.lower() or "not found" in result.output.lower()


@pytest.mark.asyncio
async def test_default_tool_executor_register_and_execute():
    from tldw_Server_API.app.core.Agent_Client_Protocol.tool_executor import DefaultToolExecutor, ToolResult

    executor = DefaultToolExecutor()

    async def echo_tool(arguments: dict) -> ToolResult:
        return ToolResult(output=f"echo: {arguments.get('text', '')}", is_error=False)

    executor.register_tool("echo", echo_tool)
    result = await executor.execute("echo", {"text": "hello"})
    assert result.output == "echo: hello"
    assert result.is_error is False


@pytest.mark.asyncio
async def test_default_tool_executor_list_tools():
    from tldw_Server_API.app.core.Agent_Client_Protocol.tool_executor import DefaultToolExecutor, ToolResult

    executor = DefaultToolExecutor()

    async def noop(args: dict) -> ToolResult:
        return ToolResult(output="", is_error=False)

    executor.register_tool("tool_a", noop)
    executor.register_tool("tool_b", noop)

    tools = await executor.list_tools()
    names = {t["name"] for t in tools}
    assert names == {"tool_a", "tool_b"}
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_tool_executor.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# tldw_Server_API/app/core/Agent_Client_Protocol/tool_executor.py
"""ToolExecutor — executes tools on behalf of agents in server_side/hybrid mode."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from loguru import logger


@dataclass
class ToolResult:
    """Result of a tool execution."""
    output: str
    is_error: bool
    duration_ms: int = 0


class ToolExecutor(ABC):
    """Executes tools on behalf of agents in server_side/hybrid mode."""

    @abstractmethod
    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        """Run a tool and return its result."""

    @abstractmethod
    async def list_tools(self) -> list[dict[str, Any]]:
        """Return available server-side tools."""


ToolHandler = Callable[[dict[str, Any]], Awaitable[ToolResult]]


class DefaultToolExecutor(ToolExecutor):
    """Default implementation with a registry of tool handlers."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolHandler] = {}

    def register_tool(self, name: str, handler: ToolHandler) -> None:
        """Register a tool handler."""
        self._tools[name] = handler

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        handler = self._tools.get(tool_name)
        if handler is None:
            return ToolResult(
                output=f"Tool not found: {tool_name}",
                is_error=True,
            )
        try:
            return await handler(arguments)
        except Exception as e:
            logger.exception(f"ToolExecutor: error executing {tool_name}")
            return ToolResult(output=str(e), is_error=True)

    async def list_tools(self) -> list[dict[str, Any]]:
        return [{"name": name} for name in self._tools]
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_tool_executor.py -v`
Expected: 4 PASSED

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Agent_Client_Protocol/tool_executor.py
git add tldw_Server_API/tests/Agent_Client_Protocol/test_tool_executor.py
git commit -m "feat(acp): add ToolExecutor interface and DefaultToolExecutor"
```

---

### Task 10: SandboxBridge

**Files:**
- Create: `tldw_Server_API/app/core/Agent_Client_Protocol/sandbox_bridge.py`
- Test: `tldw_Server_API/tests/Agent_Client_Protocol/test_sandbox_bridge.py`

**Step 1: Write the failing test**

```python
# tldw_Server_API/tests/Agent_Client_Protocol/test_sandbox_bridge.py
"""Unit tests for SandboxBridge."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock
from dataclasses import dataclass

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_sandbox_bridge_provision_returns_handle():
    from tldw_Server_API.app.core.Agent_Client_Protocol.sandbox_bridge import (
        SandboxBridge,
        SandboxProvisionRequest,
        SandboxHandle,
    )

    mock_service = AsyncMock()
    mock_service.create_session = AsyncMock(return_value=MagicMock(
        id="sandbox-sess-1",
        host="127.0.0.1",
        port=8080,
        ssh_endpoint="ssh://127.0.0.1:2222",
    ))
    mock_service.start_run = AsyncMock(return_value=MagicMock(
        id="run-1",
        stdin=None,
        stdout=None,
    ))

    bridge = SandboxBridge(sandbox_service=mock_service)
    handle = await bridge.provision(SandboxProvisionRequest(
        user_id=1,
        agent_command="claude",
        agent_args=["--chat"],
    ))

    assert isinstance(handle, SandboxHandle)
    assert handle.sandbox_session_id == "sandbox-sess-1"
    assert handle.run_id == "run-1"


@pytest.mark.asyncio
async def test_sandbox_bridge_teardown():
    from tldw_Server_API.app.core.Agent_Client_Protocol.sandbox_bridge import (
        SandboxBridge,
        SandboxHandle,
    )

    mock_service = AsyncMock()
    bridge = SandboxBridge(sandbox_service=mock_service)

    handle = SandboxHandle(
        sandbox_session_id="s1",
        run_id="r1",
    )
    await bridge.teardown(handle)

    mock_service.cancel_run.assert_awaited_once_with("r1")
    mock_service.delete_session.assert_awaited_once_with("s1")
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_sandbox_bridge.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# tldw_Server_API/app/core/Agent_Client_Protocol/sandbox_bridge.py
"""SandboxBridge — integration seam between ACP and the Sandbox module."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class SandboxProvisionRequest:
    """What ACP needs to provision a sandbox environment."""
    user_id: int
    agent_command: str
    agent_args: list[str] = field(default_factory=list)
    agent_env: dict[str, str] = field(default_factory=dict)
    runtime: str | None = None  # None = use default
    trust_level: str = "standard"
    ttl_sec: int = 86400
    network_policy: str = "deny_all"
    workspace_files: list[str] | None = None


@dataclass
class SandboxHandle:
    """Opaque handle to a provisioned sandbox environment."""
    sandbox_session_id: str
    run_id: str
    process_stdin: Any | None = None
    process_stdout: Any | None = None
    endpoint: str | None = None
    ssh_endpoint: str | None = None


class SandboxBridge:
    """Translates between ACP session needs and Sandbox module capabilities."""

    def __init__(self, sandbox_service: Any) -> None:
        self._sandbox = sandbox_service

    async def provision(self, request: SandboxProvisionRequest) -> SandboxHandle:
        """Request an execution environment for an agent session."""
        session = await self._sandbox.create_session(
            runtime=request.runtime,
            trust_level=request.trust_level,
            ttl_sec=request.ttl_sec,
            user_id=request.user_id,
            network_policy=request.network_policy,
        )

        run = await self._sandbox.start_run(
            session_id=session.id,
            command=request.agent_command,
            args=request.agent_args,
            env=request.agent_env,
        )

        return SandboxHandle(
            sandbox_session_id=session.id,
            run_id=run.id,
            process_stdin=getattr(run, "stdin", None),
            process_stdout=getattr(run, "stdout", None),
            endpoint=f"http://{getattr(session, 'host', '127.0.0.1')}:{getattr(session, 'port', 8080)}",
            ssh_endpoint=getattr(session, "ssh_endpoint", None),
        )

    async def teardown(self, handle: SandboxHandle) -> None:
        """Destroy the sandbox environment."""
        try:
            await self._sandbox.cancel_run(handle.run_id)
        except Exception:
            logger.debug(f"SandboxBridge: cancel_run failed for {handle.run_id}")
        await self._sandbox.delete_session(handle.sandbox_session_id)

    async def snapshot(self, handle: SandboxHandle) -> str:
        """Snapshot current workspace state. Returns snapshot_id."""
        return await self._sandbox.create_snapshot(handle.sandbox_session_id)

    async def restore(self, handle: SandboxHandle, snapshot_id: str) -> None:
        """Restore workspace to a previous snapshot."""
        await self._sandbox.restore_snapshot(handle.sandbox_session_id, snapshot_id)
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_sandbox_bridge.py -v`
Expected: 2 PASSED

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Agent_Client_Protocol/sandbox_bridge.py
git add tldw_Server_API/tests/Agent_Client_Protocol/test_sandbox_bridge.py
git commit -m "feat(acp): add SandboxBridge integration seam"
```

---

### Task 11: Verify All Existing ACP Tests Still Pass

**Step 1: Run the full existing ACP test suite**

Run: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/ -v --timeout=60`
Expected: All tests PASS (new code is additive, no existing code modified except adding default fields to `AgentRegistryEntry`)

**Step 2: Commit if any fixups needed**

If any tests fail due to the registry field additions, fix by ensuring defaults are backward-compatible.

---

## Phase B: MCP Adapter (Future)

> Tasks for Phase B will be planned after Phase A is complete and validated. The `MCPAdapter` will follow the same TDD pattern: test → implement → commit. It will leverage the existing `MCP_unified` module's client patterns for stdio/SSE/streamable_http transports.

## Phase C: OpenAI Tool-Use Adapter (Future)

> The `OpenAIToolUseAdapter` will implement the multi-turn tool call loop, using `httpx` for streaming HTTP. It drives the loop internally: send prompt → get tool calls → execute via `ToolExecutor` → send results → repeat.

## Phase D: ACPRunnerClient Refactor (Future)

> Incrementally refactor `runner_client.py` to use the adapter + bus + consumer architecture. The existing `ACPStdioClient` is wrapped by `StdioAdapter`. Governance, WebSocket routing, audit, and metrics are migrated to their respective consumers. The runner becomes a thin coordinator.

---

## File Map

| New File | Purpose |
|----------|---------|
| `app/core/Agent_Client_Protocol/events.py` | AgentEvent + AgentEventKind |
| `app/core/Agent_Client_Protocol/event_bus.py` | SessionEventBus |
| `app/core/Agent_Client_Protocol/governance_filter.py` | GovernanceFilter pipeline stage |
| `app/core/Agent_Client_Protocol/tool_executor.py` | ToolExecutor ABC + DefaultToolExecutor |
| `app/core/Agent_Client_Protocol/sandbox_bridge.py` | SandboxBridge integration seam |
| `app/core/Agent_Client_Protocol/adapters/__init__.py` | Adapter package exports |
| `app/core/Agent_Client_Protocol/adapters/base.py` | ProtocolAdapter ABC + AdapterConfig |
| `app/core/Agent_Client_Protocol/adapters/factory.py` | AdapterFactory |
| `app/core/Agent_Client_Protocol/adapters/stdio_adapter.py` | StdioAdapter |
| `app/core/Agent_Client_Protocol/consumers/__init__.py` | Consumer package exports |
| `app/core/Agent_Client_Protocol/consumers/base.py` | EventConsumer ABC |
| `app/core/Agent_Client_Protocol/consumers/ws_broadcaster.py` | WSBroadcaster |
| `app/core/Agent_Client_Protocol/consumers/audit_logger.py` | AuditLogger |
| `app/core/Agent_Client_Protocol/consumers/metrics_recorder.py` | MetricsRecorder |

| Modified File | Change |
|---------------|--------|
| `app/core/Agent_Client_Protocol/agent_registry.py` | 8 new fields on AgentRegistryEntry |
