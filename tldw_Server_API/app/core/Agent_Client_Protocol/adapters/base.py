"""ProtocolAdapter ABC, AdapterConfig, and PromptOptions."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable


@dataclass
class PromptOptions:
    """Options passed alongside a prompt to the adapter."""

    max_tokens: int | None = None
    timeout_sec: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class AdapterConfig:
    """Configuration handed to an adapter on connect()."""

    event_callback: Callable[..., Awaitable[None]]
    session_id: str
    protocol_config: dict[str, Any] = field(default_factory=dict)


class ProtocolAdapter(ABC):
    """Abstract base class for all protocol adapters.

    Subclasses must set ``protocol_name`` and implement every abstract method.
    """

    protocol_name: str = ""

    @abstractmethod
    async def connect(self, config: AdapterConfig) -> None:
        """Establish connection using the given configuration."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Tear down the connection."""

    @abstractmethod
    async def send_prompt(
        self,
        messages: list[dict],
        options: PromptOptions | None = None,
    ) -> None:
        """Send a prompt (list of message dicts) to the agent."""

    @abstractmethod
    async def send_tool_result(
        self,
        tool_id: str,
        output: str,
        is_error: bool = False,
    ) -> None:
        """Return a tool execution result to the agent."""

    @abstractmethod
    async def cancel(self) -> None:
        """Request cancellation of the current operation."""

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Whether the adapter currently has an active connection."""

    @property
    @abstractmethod
    def supports_streaming(self) -> bool:
        """Whether the adapter streams events or returns them in bulk."""
