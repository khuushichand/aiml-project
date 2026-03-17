"""AuditLogger -- batching event consumer that flushes to a persistence callback."""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from loguru import logger

from tldw_Server_API.app.core.Agent_Client_Protocol.consumers.base import EventConsumer
from tldw_Server_API.app.core.Agent_Client_Protocol.event_bus import SessionEventBus
from tldw_Server_API.app.core.Agent_Client_Protocol.events import AgentEvent

WriteBatchFn = Callable[[list[AgentEvent]], Awaitable[None]]


class AuditLogger(EventConsumer):
    """Buffers events and flushes them in batches to a persistence callback.

    Flushing occurs when either *batch_size* events have accumulated **or**
    *flush_interval* seconds have elapsed since the last flush, whichever
    comes first.  Any remaining events are flushed during :meth:`stop`.
    """

    consumer_id: str = "audit_logger"

    def __init__(
        self,
        write_batch_fn: WriteBatchFn,
        batch_size: int = 100,
        flush_interval: float = 5.0,
    ) -> None:
        self._write_batch_fn = write_batch_fn
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._buffer: list[AgentEvent] = []
        self._bus: SessionEventBus | None = None
        self._queue: asyncio.Queue[AgentEvent] | None = None
        self._task: asyncio.Task[None] | None = None
        self._running: bool = False

    # ------------------------------------------------------------------ #
    # EventConsumer interface
    # ------------------------------------------------------------------ #

    async def on_event(self, event: AgentEvent) -> None:
        """Buffer the event and flush if batch_size is reached."""
        self._buffer.append(event)
        if len(self._buffer) >= self._batch_size:
            await self._flush()

    async def start(self, bus: SessionEventBus) -> None:
        """Subscribe to *bus* and spawn the consume-loop task."""
        self._bus = bus
        self._queue = bus.subscribe(self.consumer_id)
        self._running = True
        self._task = asyncio.create_task(self._consume_loop())

    async def stop(self) -> None:
        """Cancel the consume loop, flush remaining buffer, and unsubscribe."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        # Flush any remaining buffered events
        if self._buffer:
            await self._flush()

        if self._bus is not None:
            self._bus.unsubscribe(self.consumer_id)
            self._bus = None

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #

    async def _flush(self) -> None:
        """Write the current buffer via write_batch_fn and clear it."""
        if not self._buffer:
            return
        batch = list(self._buffer)
        self._buffer.clear()
        try:
            await self._write_batch_fn(batch)
        except Exception:
            logger.exception(
                "AuditLogger: write_batch_fn failed for batch of {} events",
                len(batch),
            )

    async def _consume_loop(self) -> None:
        """Read events from the queue, dispatching and flushing on interval."""
        assert self._queue is not None  # noqa: S101
        while self._running:
            try:
                event = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=self._flush_interval,
                )
                await self.on_event(event)
            except asyncio.TimeoutError:
                # Interval elapsed -- flush partial buffer
                await self._flush()
            except asyncio.CancelledError:
                break
