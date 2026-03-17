"""Tests for mcp_llm_caller: LLMCaller ABC, LLMResponse, LLMToolCall, mcp_tools_to_openai_format."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_llm_response_defaults():
    """LLMResponse() has text=None and tool_calls=[]."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_llm_caller import LLMResponse

    resp = LLMResponse()
    assert resp.text is None
    assert resp.tool_calls == []


def test_llm_tool_call_fields():
    """LLMToolCall stores id, name, arguments."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_llm_caller import LLMToolCall

    tc = LLMToolCall(id="tc1", name="search", arguments={"q": "hello"})
    assert tc.id == "tc1"
    assert tc.name == "search"
    assert tc.arguments == {"q": "hello"}


def test_llm_caller_is_abstract():
    """Cannot instantiate LLMCaller directly."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_llm_caller import LLMCaller

    with pytest.raises(TypeError):
        LLMCaller()


@pytest.mark.asyncio
async def test_llm_caller_concrete():
    """A concrete subclass of LLMCaller can be instantiated and called."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_llm_caller import (
        LLMCaller,
        LLMResponse,
    )

    class FakeLLM(LLMCaller):
        async def call(self, messages, tools):
            return LLMResponse(text="Hello!")

    llm = FakeLLM()
    resp = await llm.call(messages=[{"role": "user", "content": "hi"}], tools=[])
    assert resp.text == "Hello!"
    assert resp.tool_calls == []


def test_mcp_tools_to_openai_format():
    """Convert MCP tool with inputSchema to OpenAI function-calling format."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_llm_caller import (
        mcp_tools_to_openai_format,
    )

    mcp_tools = [
        {
            "name": "search",
            "description": "Search the web",
            "inputSchema": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        }
    ]
    result = mcp_tools_to_openai_format(mcp_tools)
    assert len(result) == 1
    assert result[0]["type"] == "function"
    assert result[0]["function"]["name"] == "search"
    assert result[0]["function"]["description"] == "Search the web"
    assert result[0]["function"]["parameters"]["type"] == "object"
    assert "query" in result[0]["function"]["parameters"]["properties"]


def test_mcp_tools_to_openai_format_empty():
    """Empty list returns empty list."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_llm_caller import (
        mcp_tools_to_openai_format,
    )

    assert mcp_tools_to_openai_format([]) == []


def test_mcp_tools_to_openai_format_missing_fields():
    """Tool without description/inputSchema gets defaults."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_llm_caller import (
        mcp_tools_to_openai_format,
    )

    result = mcp_tools_to_openai_format([{"name": "bare_tool"}])
    assert len(result) == 1
    func = result[0]["function"]
    assert func["name"] == "bare_tool"
    assert func["description"] == ""
    assert func["parameters"] == {"type": "object"}
