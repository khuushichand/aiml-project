"""WSBroadcaster -- fan-out events to WebSocket connections with verbosity filtering."""
from __future__ import annotations

import asyncio
import json
from typing import Any, Awaitable, Callable

from loguru import logger

from tldw_Server_API.app.core.Agent_Client_Protocol.consumers.base import EventConsumer
from tldw_Server_API.app.core.Agent_Client_Protocol.event_bus import SessionEventBus
from tldw_Server_API.app.core.Agent_Client_Protocol.events import AgentEvent, AgentEventKind

# Verbosity level -> set of event kinds that pass the filter
_SUMMARY_KINDS: frozenset[AgentEventKind] = frozenset({
    AgentEventKind.COMPLETION,
    AgentEventKind.ERROR,
    AgentEventKind.PERMISSION_REQUEST,
    AgentEventKind.PERMISSION_RESPONSE,
    AgentEventKind.STATUS_CHANGE,
})

_STRUCTURED_KINDS: frozenset[AgentEventKind] = _SUMMARY_KINDS | frozenset({
    AgentEventKind.TOOL_CALL,
    AgentEventKind.TOOL_RESULT,
    AgentEventKind.FILE_CHANGE,
    AgentEventKind.LIFECYCLE,
})

SendCallback = Callable[[str], Awaitable[None]]


class _ConnectionInfo:
    """Internal bookkeeping for a single WebSocket connection."""

    __slots__ = ("conn_id", "send_callback", "verbosity")

    def __init__(self, conn_id: str, send_callback: SendCallback, verbosity: str) -> None:
        self.conn_id = conn_id
        self.send_callback = send_callback
        self.verbosity = verbosity


class WSBroadcaster(EventConsumer):
    """Broadcasts agent events to multiple WebSocket connections.

    Each connection has an independent verbosity level that controls which
    event kinds it receives.  Supported levels:

    - ``"full"``: all events
    - ``"summary"``: completion, error, permission_request, permission_response,
      status_change
    - ``"structured"``: summary + tool_call, tool_result, file_change, lifecycle
    """

    consumer_id: str = "ws_broadcaster"

    def __init__(self) -> None:
        self._connections: dict[str, _ConnectionInfo] = {}
        self._bus: SessionEventBus | None = None
        self._queue: asyncio.Queue[AgentEvent] | None = None
        self._task: asyncio.Task[None] | None = None
        self._running: bool = False

    # ------------------------------------------------------------------ #
    # Connection management
    # ------------------------------------------------------------------ #

    def add_connection(
        self,
        conn_id: str,
        send_callback: SendCallback,
        verbosity: str = "full",
    ) -> None:
        """Register a WebSocket connection for event delivery."""
        self._connections[conn_id] = _ConnectionInfo(conn_id, send_callback, verbosity)

    def remove_connection(self, conn_id: str) -> None:
        """Unregister a WebSocket connection."""
        self._connections.pop(conn_id, None)

    def set_verbosity(self, conn_id: str, verbosity: str) -> None:
        """Change the verbosity level for an existing connection."""
        info = self._connections.get(conn_id)
        if info is not None:
            info.verbosity = verbosity

    # ------------------------------------------------------------------ #
    # EventConsumer interface
    # ------------------------------------------------------------------ #

    async def on_event(self, event: AgentEvent) -> None:
        """Fan-out *event* to all connections that pass verbosity filter."""
        msg: str | None = None  # lazily serialized

        # Iterate over a snapshot so removals during iteration are safe
        for info in list(self._connections.values()):
            if not _passes_filter(event.kind, info.verbosity):
                continue

            if msg is None:
                msg = json.dumps(event.to_dict())

            try:
                await info.send_callback(msg)
            except Exception:
                logger.warning(
                    "WSBroadcaster: send failed for conn {}, removing",
                    info.conn_id,
                )
                self.remove_connection(info.conn_id)

    async def start(self, bus: SessionEventBus) -> None:
        """Subscribe to *bus* and spawn the consume-loop task."""
        self._bus = bus
        self._queue = bus.subscribe(self.consumer_id)
        self._running = True
        self._task = asyncio.create_task(self._consume_loop())

    async def stop(self) -> None:
        """Cancel the consume loop and unsubscribe."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._bus is not None:
            self._bus.unsubscribe(self.consumer_id)
            self._bus = None

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #

    async def _consume_loop(self) -> None:
        """Read events from the queue and dispatch to connections."""
        assert self._queue is not None  # noqa: S101
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self.on_event(event)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break


def _passes_filter(kind: AgentEventKind, verbosity: str) -> bool:
    """Return True if *kind* should be sent at *verbosity* level."""
    if verbosity == "full":
        return True
    if verbosity == "structured":
        return kind in _STRUCTURED_KINDS
    if verbosity == "summary":
        return kind in _SUMMARY_KINDS
    # Unknown verbosity -- default to full
    return True
