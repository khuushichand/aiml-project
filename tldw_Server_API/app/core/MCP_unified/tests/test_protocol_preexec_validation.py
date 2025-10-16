import pytest

from tldw_Server_API.app.core.MCP_unified.protocol import MCPProtocol, MCPRequest, RequestContext
from tldw_Server_API.app.core.MCP_unified.modules.base import BaseModule, ModuleConfig, create_tool_definition
from tldw_Server_API.app.core.MCP_unified.modules.registry import get_module_registry
from tldw_Server_API.app.core.MCP_unified.config import get_config
from tldw_Server_API.app.core.MCP_unified.monitoring.metrics import get_metrics_collector


class AllowAllRBAC:
    async def check_permission(self, *args, **kwargs):
        return True


class DummyWriteModuleNoValidator(BaseModule):
    async def on_initialize(self) -> None:
        return None

    async def on_shutdown(self) -> None:
        return None

    async def check_health(self) -> dict:
        return {"ready": True}

    async def get_tools(self) -> list[dict]:
        # Mark as write via metadata.category
        return [
            create_tool_definition(
                name="write_echo",
                description="Echo a message (write tool)",
                parameters={
                    "properties": {"message": {"type": "string"}},
                    "required": ["message"],
                },
                metadata={"category": "ingestion"},
            )
        ]

    async def execute_tool(self, tool_name: str, arguments: dict, context=None):
        return str(arguments.get("message", ""))


class DummyWriteModuleWithValidator(BaseModule):
    async def on_initialize(self) -> None:
        return None

    async def on_shutdown(self) -> None:
        return None

    async def check_health(self) -> dict:
        return {"ready": True}

    async def get_tools(self) -> list[dict]:
        # No metadata but name indicates write (heuristic)
        return [
            create_tool_definition(
                name="delete_item",
                description="Delete an item (write tool)",
                parameters={
                    "properties": {"id": {"type": "string"}},
                    "required": ["id"],
                },
            )
        ]

    def validate_tool_arguments(self, tool_name: str, arguments: dict):
        # Strict check for required field
        if tool_name == "delete_item":
            if not isinstance(arguments, dict) or "id" not in arguments or not arguments["id"]:
                raise ValueError("'id' is required")

    async def execute_tool(self, tool_name: str, arguments: dict, context=None):
        return f"deleted:{arguments.get('id')}"


@pytest.mark.asyncio
async def test_preexec_blocks_write_tool_without_validator():
    registry = get_module_registry()
    await registry.register_module("dummy_no_validator", DummyWriteModuleNoValidator, ModuleConfig(name="dummy_no_validator"))

    proto = MCPProtocol()
    # allow RBAC
    proto.rbac_policy = AllowAllRBAC()

    req = MCPRequest(method="tools/call", params={"name": "write_echo", "arguments": {"message": "hi"}}, id="t1")
    ctx = RequestContext(request_id="r1", user_id="u1", client_id="c1")

    resp = await proto.process_request(req, ctx)
    assert resp.error is not None
    assert resp.error.code == -32602  # INVALID_PARAMS
    assert "requires module.validate_tool_arguments" in (resp.error.message or "")
    # Metrics: validator missing counter incremented
    metrics = get_metrics_collector()
    entries = metrics._metrics.get("tool_validator_missing")  # type: ignore[attr-defined]
    assert entries and any(getattr(e, "labels", {}).get("tool") == "write_echo" for e in entries)


@pytest.mark.asyncio
async def test_preexec_calls_validator_and_maps_failure():
    registry = get_module_registry()
    await registry.register_module("dummy_with_validator", DummyWriteModuleWithValidator, ModuleConfig(name="dummy_with_validator"))

    proto = MCPProtocol()
    proto.rbac_policy = AllowAllRBAC()

    # Missing id should trigger INVALID_PARAMS via protocol guard
    bad_req = MCPRequest(method="tools/call", params={"name": "delete_item", "arguments": {}}, id="t2")
    ctx = RequestContext(request_id="r2", user_id="u2", client_id="c2")
    bad_resp = await proto.process_request(bad_req, ctx)
    assert bad_resp.error is not None
    assert bad_resp.error.code == -32602
    # Metrics: invalid params counter incremented
    metrics = get_metrics_collector()
    entries = metrics._metrics.get("tool_invalid_params")  # type: ignore[attr-defined]
    assert entries and any(getattr(e, "labels", {}).get("tool") == "delete_item" for e in entries)

    # Valid request should succeed
    ok_req = MCPRequest(method="tools/call", params={"name": "delete_item", "arguments": {"id": "123"}}, id="t3")
    ok_resp = await proto.process_request(ok_req, ctx)
    assert ok_resp.error is None
    assert ok_resp.result is not None
    assert any(part.get("text") == "deleted:123" for part in ok_resp.result.get("content", []))


class DummyReadModuleWithSchema(BaseModule):
    async def on_initialize(self) -> None:
        return None

    async def on_shutdown(self) -> None:
        return None

    async def check_health(self) -> dict:
        return {"ready": True}

    async def get_tools(self) -> list[dict]:
        tool = create_tool_definition(
            name="echo_read",
            description="Echo with schema",
            parameters={
                "properties": {
                    "x": {"type": "string"},
                    "y": {"type": "integer"}
                },
                "required": ["x"],
            },
            metadata={"category": "read"},
        )
        try:
            tool["inputSchema"]["additionalProperties"] = False
        except Exception:
            pass
        return [tool]

    async def execute_tool(self, tool_name: str, arguments: dict, context=None):
        return f"{arguments.get('x')}:{arguments.get('y')}"


@pytest.mark.asyncio
async def test_schema_validation_required_type_and_unknown():
    # Ensure config has schema validation enabled
    try:
        get_config.cache_clear()  # type: ignore[attr-defined]
    except Exception:
        pass

    registry = get_module_registry()
    await registry.register_module("dummy_read_schema", DummyReadModuleWithSchema, ModuleConfig(name="dummy_read_schema"))

    proto = MCPProtocol()
    proto.rbac_policy = AllowAllRBAC()
    ctx = RequestContext(request_id="s1", user_id="u1", client_id="c1")

    # Missing required 'x'
    r1 = MCPRequest(method="tools/call", params={"name": "echo_read", "arguments": {"y": 1}}, id="s1")
    resp1 = await proto.process_request(r1, ctx)
    assert resp1.error and resp1.error.code == -32602

    # Wrong type for y
    r2 = MCPRequest(method="tools/call", params={"name": "echo_read", "arguments": {"x": "ok", "y": "bad"}}, id="s2")
    resp2 = await proto.process_request(r2, ctx)
    assert resp2.error and resp2.error.code == -32602

    r3 = MCPRequest(method="tools/call", params={"name": "echo_read", "arguments": {"x": "ok", "y": 2, "z": 9}}, id="s3")
    resp3 = await proto.process_request(r3, ctx)
    assert resp3.error and resp3.error.code == -32602

    # Valid
    r4 = MCPRequest(method="tools/call", params={"name": "echo_read", "arguments": {"x": "ok", "y": 2}}, id="s4")
    resp4 = await proto.process_request(r4, ctx)
    assert resp4.error is None
    assert any(part.get("text") == "ok:2" for part in resp4.result.get("content", []))


@pytest.mark.asyncio
async def test_disable_write_tools_gate(monkeypatch):
    # Force-disable write tools for this test by tweaking cached config
    try:
        cfg = get_config()
        setattr(cfg, "disable_write_tools", True)
    except Exception:
        pass

    registry = get_module_registry()
    await registry.register_module("dummy_write_disabled", DummyWriteModuleWithValidator, ModuleConfig(name="dummy_write_disabled"))

    proto = MCPProtocol()
    proto.rbac_policy = AllowAllRBAC()
    ctx = RequestContext(request_id="dw1", user_id="u1", client_id="c1")
    # Sanity check config gate
    assert get_config().disable_write_tools is True

    req = MCPRequest(method="tools/call", params={"name": "delete_item", "arguments": {"id": "123"}}, id="dw1")
    resp = await proto.process_request(req, ctx)
    assert resp.error is not None
    assert resp.error.code == -32001  # AUTHORIZATION_ERROR
