"""Unit tests for StdioAdapter wrapping ACPStdioClient."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.unit


def test_stdio_adapter_protocol_name():
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.stdio_adapter import StdioAdapter

    adapter = StdioAdapter()
    assert adapter.protocol_name == "stdio"


def test_stdio_adapter_not_connected_initially():
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.stdio_adapter import StdioAdapter

    adapter = StdioAdapter()
    assert adapter.is_connected is False


def test_stdio_adapter_supports_streaming():
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.stdio_adapter import StdioAdapter

    adapter = StdioAdapter()
    assert adapter.supports_streaming is True


@pytest.mark.asyncio
async def test_stdio_adapter_connect_sets_connected():
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.stdio_adapter import StdioAdapter
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.base import AdapterConfig

    mock_client = AsyncMock()
    mock_client.is_running = True

    adapter = StdioAdapter()
    config = AdapterConfig(
        event_callback=AsyncMock(),
        session_id="sess-1",
        protocol_config={"client": mock_client},
    )
    await adapter.connect(config)
    assert adapter.is_connected is True
    mock_client.set_notification_handler.assert_called_once()


@pytest.mark.asyncio
async def test_stdio_adapter_connect_rejects_unstarted_client():
    """connect() should raise RuntimeError if the client process is not running."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.stdio_adapter import StdioAdapter
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.base import AdapterConfig

    mock_client = AsyncMock()
    mock_client.is_running = False  # process not started

    adapter = StdioAdapter()
    config = AdapterConfig(
        event_callback=AsyncMock(),
        session_id="sess-1",
        protocol_config={"client": mock_client},
    )
    with pytest.raises(RuntimeError, match="not running"):
        await adapter.connect(config)
    assert adapter.is_connected is False


@pytest.mark.asyncio
async def test_stdio_adapter_translates_completion_notification():
    """Simulate a result notification with type=text and verify COMPLETION event."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.stdio_adapter import StdioAdapter
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.base import AdapterConfig
    from tldw_Server_API.app.core.Agent_Client_Protocol.events import AgentEventKind
    from tldw_Server_API.app.core.Agent_Client_Protocol.stdio_client import ACPMessage

    received_events = []

    async def capture(event):
        received_events.append(event)

    mock_client = AsyncMock()
    mock_client.is_running = True

    adapter = StdioAdapter()
    config = AdapterConfig(
        event_callback=capture,
        session_id="sess-1",
        protocol_config={"client": mock_client},
    )
    await adapter.connect(config)

    # Extract the notification handler that was set on the client
    handler = mock_client.set_notification_handler.call_args[0][0]

    # Simulate a completion notification
    notification = ACPMessage(
        jsonrpc="2.0",
        method="result",
        params={"type": "text", "text": "Hello world", "stop_reason": "end_turn"},
    )
    await handler(notification)

    assert len(received_events) == 1
    ev = received_events[0]
    assert ev.kind == AgentEventKind.COMPLETION
    assert ev.session_id == "sess-1"
    assert ev.payload["text"] == "Hello world"


@pytest.mark.asyncio
async def test_stdio_adapter_translates_tool_use_notification():
    """Simulate an update notification with type=tool_use and verify TOOL_CALL event."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.stdio_adapter import StdioAdapter
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.base import AdapterConfig
    from tldw_Server_API.app.core.Agent_Client_Protocol.events import AgentEventKind
    from tldw_Server_API.app.core.Agent_Client_Protocol.stdio_client import ACPMessage

    received_events = []

    async def capture(event):
        received_events.append(event)

    mock_client = AsyncMock()
    mock_client.is_running = True

    adapter = StdioAdapter()
    config = AdapterConfig(
        event_callback=capture,
        session_id="sess-2",
        protocol_config={"client": mock_client},
    )
    await adapter.connect(config)

    handler = mock_client.set_notification_handler.call_args[0][0]

    notification = ACPMessage(
        jsonrpc="2.0",
        method="update",
        params={
            "type": "tool_use",
            "tool_id": "t1",
            "tool_name": "bash",
            "arguments": {"cmd": "ls"},
        },
    )
    await handler(notification)

    assert len(received_events) == 1
    ev = received_events[0]
    assert ev.kind == AgentEventKind.TOOL_CALL
    assert ev.payload["tool_name"] == "bash"
    assert ev.payload["tool_id"] == "t1"
    assert "permission_tier" in ev.payload


@pytest.mark.asyncio
async def test_stdio_adapter_translates_thinking_notification():
    """Simulate an update notification with type=thinking."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.stdio_adapter import StdioAdapter
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.base import AdapterConfig
    from tldw_Server_API.app.core.Agent_Client_Protocol.events import AgentEventKind
    from tldw_Server_API.app.core.Agent_Client_Protocol.stdio_client import ACPMessage

    received_events = []

    async def capture(event):
        received_events.append(event)

    mock_client = AsyncMock()
    mock_client.is_running = True

    adapter = StdioAdapter()
    config = AdapterConfig(
        event_callback=capture,
        session_id="sess-3",
        protocol_config={"client": mock_client},
    )
    await adapter.connect(config)

    handler = mock_client.set_notification_handler.call_args[0][0]

    notification = ACPMessage(
        jsonrpc="2.0",
        method="update",
        params={"type": "thinking", "text": "Let me think..."},
    )
    await handler(notification)

    assert len(received_events) == 1
    assert received_events[0].kind == AgentEventKind.THINKING


@pytest.mark.asyncio
async def test_stdio_adapter_translates_error_notification():
    """Simulate an error notification."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.stdio_adapter import StdioAdapter
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.base import AdapterConfig
    from tldw_Server_API.app.core.Agent_Client_Protocol.events import AgentEventKind
    from tldw_Server_API.app.core.Agent_Client_Protocol.stdio_client import ACPMessage

    received_events = []

    async def capture(event):
        received_events.append(event)

    mock_client = AsyncMock()
    mock_client.is_running = True

    adapter = StdioAdapter()
    config = AdapterConfig(
        event_callback=capture,
        session_id="sess-4",
        protocol_config={"client": mock_client},
    )
    await adapter.connect(config)

    handler = mock_client.set_notification_handler.call_args[0][0]

    notification = ACPMessage(
        jsonrpc="2.0",
        method="error",
        params={"message": "something broke"},
    )
    await handler(notification)

    assert len(received_events) == 1
    assert received_events[0].kind == AgentEventKind.ERROR
    assert received_events[0].payload["message"] == "something broke"


@pytest.mark.asyncio
async def test_stdio_adapter_translates_tool_result_from_update():
    """Simulate an update notification with type=tool_result."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.stdio_adapter import StdioAdapter
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.base import AdapterConfig
    from tldw_Server_API.app.core.Agent_Client_Protocol.events import AgentEventKind
    from tldw_Server_API.app.core.Agent_Client_Protocol.stdio_client import ACPMessage

    received_events = []

    async def capture(event):
        received_events.append(event)

    mock_client = AsyncMock()
    mock_client.is_running = True

    adapter = StdioAdapter()
    config = AdapterConfig(
        event_callback=capture,
        session_id="sess-5",
        protocol_config={"client": mock_client},
    )
    await adapter.connect(config)

    handler = mock_client.set_notification_handler.call_args[0][0]

    notification = ACPMessage(
        jsonrpc="2.0",
        method="update",
        params={"type": "tool_result", "tool_id": "t1", "output": "file.txt"},
    )
    await handler(notification)

    assert len(received_events) == 1
    assert received_events[0].kind == AgentEventKind.TOOL_RESULT


@pytest.mark.asyncio
async def test_stdio_adapter_translates_permission_request():
    """Simulate an update notification with type=permission_request."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.stdio_adapter import StdioAdapter
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.base import AdapterConfig
    from tldw_Server_API.app.core.Agent_Client_Protocol.events import AgentEventKind
    from tldw_Server_API.app.core.Agent_Client_Protocol.stdio_client import ACPMessage

    received_events = []

    async def capture(event):
        received_events.append(event)

    mock_client = AsyncMock()
    mock_client.is_running = True

    adapter = StdioAdapter()
    config = AdapterConfig(
        event_callback=capture,
        session_id="sess-6",
        protocol_config={"client": mock_client},
    )
    await adapter.connect(config)

    handler = mock_client.set_notification_handler.call_args[0][0]

    notification = ACPMessage(
        jsonrpc="2.0",
        method="update",
        params={"type": "permission_request", "request_id": "r1", "tool_name": "bash"},
    )
    await handler(notification)

    assert len(received_events) == 1
    assert received_events[0].kind == AgentEventKind.PERMISSION_REQUEST


@pytest.mark.asyncio
async def test_stdio_adapter_disconnect():
    """Verify disconnect calls client.close()."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.stdio_adapter import StdioAdapter
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.base import AdapterConfig

    mock_client = AsyncMock()
    mock_client.is_running = True

    adapter = StdioAdapter()
    config = AdapterConfig(
        event_callback=AsyncMock(),
        session_id="sess-7",
        protocol_config={"client": mock_client},
    )
    await adapter.connect(config)
    assert adapter.is_connected is True

    await adapter.disconnect()
    mock_client.close.assert_awaited_once()
    assert adapter.is_connected is False


@pytest.mark.asyncio
async def test_stdio_adapter_send_prompt():
    """Verify send_prompt calls client.call with correct args."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.stdio_adapter import StdioAdapter
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.base import AdapterConfig

    mock_client = AsyncMock()
    mock_client.is_running = True

    adapter = StdioAdapter()
    config = AdapterConfig(
        event_callback=AsyncMock(),
        session_id="sess-8",
        protocol_config={"client": mock_client},
    )
    await adapter.connect(config)

    messages = [{"role": "user", "content": "Hello"}]
    await adapter.send_prompt(messages)

    mock_client.call.assert_awaited_once_with("prompt", {"messages": messages})


@pytest.mark.asyncio
async def test_stdio_adapter_send_tool_result():
    """Verify send_tool_result calls client.call with correct args."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.stdio_adapter import StdioAdapter
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.base import AdapterConfig

    mock_client = AsyncMock()
    mock_client.is_running = True

    adapter = StdioAdapter()
    config = AdapterConfig(
        event_callback=AsyncMock(),
        session_id="sess-9",
        protocol_config={"client": mock_client},
    )
    await adapter.connect(config)

    await adapter.send_tool_result("t1", "output data", is_error=True)

    mock_client.call.assert_awaited_once_with(
        "tool_result",
        {"tool_id": "t1", "output": "output data", "is_error": True},
    )


@pytest.mark.asyncio
async def test_stdio_adapter_cancel():
    """Verify cancel calls client.notify."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.stdio_adapter import StdioAdapter
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.base import AdapterConfig

    mock_client = AsyncMock()
    mock_client.is_running = True

    adapter = StdioAdapter()
    config = AdapterConfig(
        event_callback=AsyncMock(),
        session_id="sess-10",
        protocol_config={"client": mock_client},
    )
    await adapter.connect(config)

    await adapter.cancel()

    mock_client.notify.assert_awaited_once_with("cancel", {})
