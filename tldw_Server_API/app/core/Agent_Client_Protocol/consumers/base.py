"""EventConsumer ABC -- base class for all event bus consumers."""
from __future__ import annotations

from abc import ABC, abstractmethod

from tldw_Server_API.app.core.Agent_Client_Protocol.event_bus import SessionEventBus
from tldw_Server_API.app.core.Agent_Client_Protocol.events import AgentEvent


class EventConsumer(ABC):
    """Abstract base class for event bus consumers.

    Each consumer subscribes to a :class:`SessionEventBus`, receives events
    through its queue, and processes them according to its purpose.
    """

    consumer_id: str

    @abstractmethod
    async def on_event(self, event: AgentEvent) -> None:
        """Handle a single event. Subclasses must implement this."""

    @abstractmethod
    async def start(self, bus: SessionEventBus) -> None:
        """Subscribe to *bus* and begin consuming events."""

    @abstractmethod
    async def stop(self) -> None:
        """Cancel the consume loop and unsubscribe from the bus."""
