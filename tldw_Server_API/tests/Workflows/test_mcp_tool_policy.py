import pytest

from tldw_Server_API.app.core.Workflows.adapters import run_mcp_tool_adapter
from tldw_Server_API.app.core.exceptions import AdapterError


pytestmark = pytest.mark.unit


class _DummyModule:
    async def get_tools(self):
        return [
            {"name": "echo", "metadata": {"scopes": ["read"]}},
        ]

    async def execute_tool(self, tool_name, arguments):
        if tool_name != "echo":
            raise ValueError("unknown tool")
        return {"message": arguments.get("message")}


class _DummyRegistry:
    def __init__(self):
        self._tool_registry = {"echo": "dummy"}
        self._module_instances = {"dummy": _DummyModule()}


class _DummyServer:
    def __init__(self):
        self.module_registry = _DummyRegistry()


@pytest.mark.asyncio
async def test_mcp_tool_policy_allows(monkeypatch):
    import tldw_Server_API.app.core.MCP_unified as mcp_mod

    monkeypatch.setattr(mcp_mod, "get_mcp_server", lambda: _DummyServer())
    config = {"tool_name": "echo", "arguments": {"message": "hi"}}
    context = {"workflow_metadata": {"mcp": {"allowlist": ["echo"], "scopes": ["read"]}}}
    result = await run_mcp_tool_adapter(config, context)
    assert result["result"]["message"] == "hi"


@pytest.mark.asyncio
async def test_mcp_tool_policy_blocks_allowlist(monkeypatch):
    import tldw_Server_API.app.core.MCP_unified as mcp_mod

    monkeypatch.setattr(mcp_mod, "get_mcp_server", lambda: _DummyServer())
    config = {"tool_name": "echo", "arguments": {"message": "hi"}}
    context = {"workflow_metadata": {"mcp": {"allowlist": ["media.search"], "scopes": ["read"]}}}
    with pytest.raises(AdapterError, match="mcp_tool_not_allowed"):
        await run_mcp_tool_adapter(config, context)


@pytest.mark.asyncio
async def test_mcp_tool_policy_blocks_missing_scope(monkeypatch):
    import tldw_Server_API.app.core.MCP_unified as mcp_mod

    monkeypatch.setattr(mcp_mod, "get_mcp_server", lambda: _DummyServer())
    config = {"tool_name": "echo", "arguments": {"message": "hi"}}
    context = {"workflow_metadata": {"mcp": {"allowlist": ["echo"], "scopes": ["write"]}}}
    with pytest.raises(AdapterError, match="mcp_tool_scope_denied"):
        await run_mcp_tool_adapter(config, context)
