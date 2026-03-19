"""Tests for ToolExecutor interface and DefaultToolExecutor (Task 9)."""
from __future__ import annotations

import asyncio
import pytest

from tldw_Server_API.app.core.Agent_Client_Protocol.tool_executor import (
    DefaultToolExecutor,
    ToolExecutor,
    ToolResult,
)


class TestToolExecutorIsAbstract:
    """ToolExecutor cannot be instantiated directly."""

    def test_tool_executor_is_abstract(self) -> None:
        with pytest.raises(TypeError):
            ToolExecutor()  # type: ignore[abstract]


class TestDefaultToolExecutorUnknownToolReturnsError:
    """Executing an unknown tool returns an error ToolResult."""

    @pytest.mark.asyncio
    async def test_default_tool_executor_unknown_tool_returns_error(self) -> None:
        executor = DefaultToolExecutor()
        result = await executor.execute("nonexistent_tool", {})
        assert isinstance(result, ToolResult)
        assert result.is_error is True
        assert "nonexistent_tool" in result.output


class TestDefaultToolExecutorRegisterAndExecute:
    """Registering a tool handler and executing it returns expected output."""

    @pytest.mark.asyncio
    async def test_default_tool_executor_register_and_execute(self) -> None:
        executor = DefaultToolExecutor()

        async def echo_handler(arguments: dict) -> ToolResult:
            return ToolResult(output=f"echo: {arguments.get('msg', '')}", is_error=False)

        executor.register_tool("echo", echo_handler)
        result = await executor.execute("echo", {"msg": "hello"})

        assert isinstance(result, ToolResult)
        assert result.is_error is False
        assert result.output == "echo: hello"
        assert result.duration_ms >= 0


class TestDefaultToolExecutorListTools:
    """list_tools returns registered tool names."""

    @pytest.mark.asyncio
    async def test_default_tool_executor_list_tools(self) -> None:
        executor = DefaultToolExecutor()

        # Empty initially
        tools = await executor.list_tools()
        assert tools == []

        async def noop_handler(arguments: dict) -> ToolResult:
            return ToolResult(output="ok", is_error=False)

        executor.register_tool("tool_a", noop_handler)
        executor.register_tool("tool_b", noop_handler)

        tools = await executor.list_tools()
        names = {t["name"] for t in tools}
        assert names == {"tool_a", "tool_b"}
