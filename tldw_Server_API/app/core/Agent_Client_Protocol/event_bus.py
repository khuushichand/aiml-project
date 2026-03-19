"""SessionEventBus -- per-session async event fan-out with monotonic sequencing."""
from __future__ import annotations

import asyncio
from collections import deque

from loguru import logger

from tldw_Server_API.app.core.Agent_Client_Protocol.events import AgentEvent


class SessionEventBus:
    """Fan-out event bus scoped to a single agent session.

    Events are assigned monotonically increasing sequence numbers and kept in a
    bounded ring buffer for snapshot/replay.  Subscribers receive events via
    individual ``asyncio.Queue`` instances.
    """

    def __init__(
        self,
        session_id: str,
        max_buffer: int = 10_000,
        subscriber_queue_size: int = 1_000,
    ) -> None:
        self._session_id = session_id
        self._subscriber_queue_size = subscriber_queue_size
        self._sequence: int = 0
        self._buffer: deque[AgentEvent] = deque(maxlen=max_buffer)
        self._subscribers: dict[str, asyncio.Queue[AgentEvent]] = {}

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def current_sequence(self) -> int:
        """Last assigned sequence number (0 if nothing published yet)."""
        return self._sequence

    @property
    def min_sequence(self) -> int:
        """Lowest sequence number still available in the buffer."""
        if self._buffer:
            return self._buffer[0].sequence
        return 0

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    async def publish(self, event: AgentEvent) -> None:
        """Assign a sequence number and distribute *event* to all subscribers."""
        self._sequence += 1
        event.sequence = self._sequence
        self._buffer.append(event)
        self._distribute(event)

    async def inject(self, event: AgentEvent) -> None:
        """Alias for :meth:`publish` -- used for externally-sourced events."""
        await self.publish(event)

    # ------------------------------------------------------------------
    # Subscription
    # ------------------------------------------------------------------

    def subscribe(
        self,
        consumer_id: str,
        from_sequence: int = 0,
    ) -> asyncio.Queue[AgentEvent]:
        """Create a bounded queue for *consumer_id* and optionally replay history.

        Parameters
        ----------
        consumer_id:
            Unique identifier for the subscriber.
        from_sequence:
            If > 0, replay buffered events starting at this sequence number.

        Returns
        -------
        asyncio.Queue that will receive future (and replayed) events.
        """
        queue: asyncio.Queue[AgentEvent] = asyncio.Queue(
            maxsize=self._subscriber_queue_size,
        )
        self._subscribers[consumer_id] = queue

        if from_sequence > 0:
            for ev in self._buffer:
                if ev.sequence >= from_sequence:
                    try:
                        queue.put_nowait(ev)
                    except asyncio.QueueFull:
                        logger.warning(
                            "Replay overflow for subscriber {} at seq {}",
                            consumer_id,
                            ev.sequence,
                        )
                        break

        return queue

    def unsubscribe(self, consumer_id: str) -> None:
        """Remove *consumer_id* so it no longer receives events."""
        self._subscribers.pop(consumer_id, None)

    # ------------------------------------------------------------------
    # Snapshot / replay
    # ------------------------------------------------------------------

    def snapshot(self, from_sequence: int = 0) -> list[AgentEvent]:
        """Return buffered events, optionally filtered by *from_sequence*."""
        if from_sequence <= 0:
            return list(self._buffer)
        return [ev for ev in self._buffer if ev.sequence >= from_sequence]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _distribute(self, event: AgentEvent) -> None:
        """Push *event* to every subscriber queue (non-blocking)."""
        for consumer_id, queue in self._subscribers.items():
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(
                    "Event bus dropping event seq {} for subscriber {} (queue full)",
                    event.sequence,
                    consumer_id,
                )
