"""MetricsRecorder -- lightweight event counter by kind."""
from __future__ import annotations

import asyncio
from collections import Counter

from tldw_Server_API.app.core.Agent_Client_Protocol.consumers.base import EventConsumer
from tldw_Server_API.app.core.Agent_Client_Protocol.event_bus import SessionEventBus
from tldw_Server_API.app.core.Agent_Client_Protocol.events import AgentEvent


class MetricsRecorder(EventConsumer):
    """Counts events by :attr:`AgentEvent.kind` for lightweight metrics.

    Access :attr:`counters` to inspect counts (keyed by kind *value* string).
    """

    consumer_id: str = "metrics_recorder"

    def __init__(self) -> None:
        self.counters: Counter[str] = Counter()
        self._bus: SessionEventBus | None = None
        self._queue: asyncio.Queue[AgentEvent] | None = None
        self._task: asyncio.Task[None] | None = None
        self._running: bool = False

    # ------------------------------------------------------------------ #
    # EventConsumer interface
    # ------------------------------------------------------------------ #

    async def on_event(self, event: AgentEvent) -> None:
        """Increment the counter for the event's kind."""
        self.counters[event.kind.value] += 1

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
        """Read events from the queue and count them."""
        assert self._queue is not None  # noqa: S101
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self.on_event(event)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
