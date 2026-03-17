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
        self._stop_event: asyncio.Event = asyncio.Event()

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
        self._stop_event.clear()
        self._task = asyncio.create_task(self._consume_loop())

    async def stop(self) -> None:
        """Signal the consume loop to exit and unsubscribe."""
        self._running = False
        self._stop_event.set()
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
        if self._queue is None:
            return
        stop_task = asyncio.create_task(self._stop_event.wait())
        try:
            while self._running:
                get_task = asyncio.create_task(self._queue.get())
                done, _ = await asyncio.wait(
                    {get_task, stop_task}, return_when=asyncio.FIRST_COMPLETED,
                )
                if stop_task in done:
                    get_task.cancel()
                    break
                await self.on_event(get_task.result())
        except asyncio.CancelledError:
            pass
        finally:
            stop_task.cancel()
