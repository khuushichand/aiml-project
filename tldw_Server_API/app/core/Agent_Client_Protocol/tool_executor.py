"""ToolExecutor interface and DefaultToolExecutor implementation.

Provides an abstract base for executing tools by name, plus a default
in-memory registry-based implementation.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


@dataclass
class ToolResult:
    """Result of a tool execution."""
    output: str
    is_error: bool
    duration_ms: int = 0


# Type alias for tool handler callables
ToolHandler = Callable[[dict[str, Any]], Awaitable[ToolResult]]


class ToolExecutor(ABC):
    """Abstract base class for tool executors."""

    @abstractmethod
    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        """Execute a tool by name with the given arguments."""
        ...

    @abstractmethod
    async def list_tools(self) -> list[dict[str, Any]]:
        """List all available tools."""
        ...


class DefaultToolExecutor(ToolExecutor):
    """Default in-memory tool executor with a simple handler registry."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolHandler] = {}

    def register_tool(self, name: str, handler: ToolHandler) -> None:
        """Register a tool handler by name."""
        self._tools[name] = handler

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        """Execute a registered tool. Returns error ToolResult if not found."""
        handler = self._tools.get(tool_name)
        if handler is None:
            return ToolResult(
                output=f"Tool not found: {tool_name}",
                is_error=True,
            )
        start = time.monotonic()
        result = await handler(arguments)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        result.duration_ms = elapsed_ms
        return result

    async def list_tools(self) -> list[dict[str, Any]]:
        """Return list of registered tool descriptors."""
        return [{"name": name} for name in self._tools]
