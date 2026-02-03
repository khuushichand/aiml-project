import os

import pytest


@pytest.mark.unit
@pytest.mark.asyncio
async def test_protocol_tools_call_blocks_disallowed_tools(monkeypatch):
    os.environ["TEST_MODE"] = "true"

    from tldw_Server_API.app.core.MCP_unified.protocol import MCPProtocol, RequestContext

    class _ModuleStub:
        name = "Shell"

        async def get_tools(self):
            return [{"name": "Bash", "description": "", "inputSchema": {"type": "object"}}]

        async def execute_tool(self, tool_name, arguments, context=None):
            return {"ok": True}

        async def execute_with_circuit_breaker(self, func, *args, **kwargs):
            return await func(*args, **kwargs)

        def sanitize_input(self, args):
            return args

        def validate_tool_arguments(self, tool_name, tool_args):
            return None

        def is_write_tool_def(self, tool_def):
            return False

    class _RegistryStub:
        async def find_module_for_tool(self, tool_name):
            return _ModuleStub() if tool_name == "Bash" else None

        def get_module_id_for_tool(self, tool_name):
            return "shell"

    proto = MCPProtocol()
    proto.module_registry = _RegistryStub()

    async def _allow_mod(ctx, mid):
        return True

    async def _allow_tool(ctx, name, **_kwargs):
        return True

    proto._has_module_permission = _allow_mod  # type: ignore
    proto._has_tool_permission = _allow_tool  # type: ignore

    ctx = RequestContext(
        request_id="allowed-tools-deny",
        user_id="1",
        client_id="unit",
        session_id=None,
        metadata={"allowed_tools": ["notes.search"]},
    )

    with pytest.raises(PermissionError):
        await proto._handle_tools_call({"name": "Bash", "arguments": {"command": "git status"}}, ctx)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_protocol_tools_call_allows_command_pattern(monkeypatch):
    os.environ["TEST_MODE"] = "true"

    from tldw_Server_API.app.core.MCP_unified.protocol import MCPProtocol, RequestContext

    class _ModuleStub:
        name = "Shell"

        async def get_tools(self):
            return [{"name": "Bash", "description": "", "inputSchema": {"type": "object"}}]

        async def execute_tool(self, tool_name, arguments, context=None):
            return {"ok": True}

        async def execute_with_circuit_breaker(self, func, *args, **kwargs):
            return await func(*args, **kwargs)

        def sanitize_input(self, args):
            return args

        def validate_tool_arguments(self, tool_name, tool_args):
            return None

        def is_write_tool_def(self, tool_def):
            return False

    class _RegistryStub:
        async def find_module_for_tool(self, tool_name):
            return _ModuleStub() if tool_name == "Bash" else None

        def get_module_id_for_tool(self, tool_name):
            return "shell"

    proto = MCPProtocol()
    proto.module_registry = _RegistryStub()

    async def _allow_mod(ctx, mid):
        return True

    async def _allow_tool(ctx, name, **_kwargs):
        return True

    proto._has_module_permission = _allow_mod  # type: ignore
    proto._has_tool_permission = _allow_tool  # type: ignore

    ctx = RequestContext(
        request_id="allowed-tools-allow",
        user_id="1",
        client_id="unit",
        session_id=None,
        metadata={"allowed_tools": ["Bash(git *)"]},
    )

    result = await proto._handle_tools_call({"name": "Bash", "arguments": {"command": "git status"}}, ctx)
    assert isinstance(result, dict)
    assert result.get("tool") == "Bash"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_protocol_tools_call_blocks_command_pattern_mismatch(monkeypatch):
    os.environ["TEST_MODE"] = "true"

    from tldw_Server_API.app.core.MCP_unified.protocol import MCPProtocol, RequestContext

    class _ModuleStub:
        name = "Shell"

        async def get_tools(self):
            return [{"name": "Bash", "description": "", "inputSchema": {"type": "object"}}]

        async def execute_tool(self, tool_name, arguments, context=None):
            return {"ok": True}

        async def execute_with_circuit_breaker(self, func, *args, **kwargs):
            return await func(*args, **kwargs)

        def sanitize_input(self, args):
            return args

        def validate_tool_arguments(self, tool_name, tool_args):
            return None

        def is_write_tool_def(self, tool_def):
            return False

    class _RegistryStub:
        async def find_module_for_tool(self, tool_name):
            return _ModuleStub() if tool_name == "Bash" else None

        def get_module_id_for_tool(self, tool_name):
            return "shell"

    proto = MCPProtocol()
    proto.module_registry = _RegistryStub()

    async def _allow_mod(ctx, mid):
        return True

    async def _allow_tool(ctx, name, **_kwargs):
        return True

    proto._has_module_permission = _allow_mod  # type: ignore
    proto._has_tool_permission = _allow_tool  # type: ignore

    ctx = RequestContext(
        request_id="allowed-tools-deny-pattern",
        user_id="1",
        client_id="unit",
        session_id=None,
        metadata={"allowed_tools": ["Bash(git *)"]},
    )

    with pytest.raises(PermissionError):
        await proto._handle_tools_call({"name": "Bash", "arguments": {"command": "npm test"}}, ctx)
