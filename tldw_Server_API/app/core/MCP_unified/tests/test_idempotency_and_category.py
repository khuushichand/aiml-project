import pytest

from typing import Dict, Any

from tldw_Server_API.app.core.MCP_unified.protocol import IdempotencyManager, MCPProtocol, MCPRequest, RequestContext
from tldw_Server_API.app.core.MCP_unified.modules.base import BaseModule, ModuleConfig, create_tool_definition
from tldw_Server_API.app.core.MCP_unified.modules.registry import get_module_registry
from tldw_Server_API.app.core.MCP_unified.monitoring.metrics import get_metrics_collector


class AllowAllRBAC:
    async def check_permission(self, *args, **kwargs):
        return True


class _CountingWriteModule(BaseModule):
    def __init__(self, config: ModuleConfig):
        super().__init__(config)
        self.counter = 0

    async def on_initialize(self) -> None:
        return None

    async def on_shutdown(self) -> None:
        return None

    async def check_health(self) -> Dict[str, bool]:
        return {"ok": True}

    async def get_tools(self) -> list[Dict[str, Any]]:
        return [
            create_tool_definition(
                name="write_count",
                description="Increment and return count (write tool)",
                parameters={"properties": {"x": {"type": "string"}}, "required": ["x"]},
                metadata={"category": "ingestion"},
            )
        ]

    def validate_tool_arguments(self, tool_name: str, arguments: Dict[str, Any]):
        if tool_name == "write_count" and (not isinstance(arguments, dict) or "x" not in arguments):
            raise ValueError("x required")

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any], context=None):
        # Side effect: increment counter when actually executed
        self.counter += 1
        return f"count:{self.counter}:{arguments.get('x')}"


@pytest.mark.asyncio
async def test_idempotency_dedupes_write_calls():
    registry = get_module_registry()
    await registry.register_module("counting_write", _CountingWriteModule, ModuleConfig(name="counting_write"))

    proto = MCPProtocol()
    proto.rbac_policy = AllowAllRBAC()

    ctx = RequestContext(request_id="id1", user_id="u1", client_id="c1")

    # First call executes the tool
    req1 = MCPRequest(method="tools/call", params={
        "name": "write_count",
        "arguments": {"x": "A"},
        "idempotencyKey": "k-123",
    }, id="r1")
    resp1 = await proto.process_request(req1, ctx)
    assert resp1.error is None
    payload1 = resp1.result
    assert any(part.get("text", "").startswith("count:1:A") for part in payload1.get("content", []))

    # Second call with same idempotencyKey should not increment counter
    req2 = MCPRequest(method="tools/call", params={
        "name": "write_count",
        "arguments": {"x": "A"},
        "idempotencyKey": "k-123",
    }, id="r2")
    resp2 = await proto.process_request(req2, ctx)
    assert resp2.error is None
    payload2 = resp2.result
    assert any(part.get("text", "").startswith("count:1:A") for part in payload2.get("content", []))

    # Metrics should record one miss then one hit
    metrics = get_metrics_collector()
    hits = metrics._metrics.get("idempotency_hit")
    misses = metrics._metrics.get("idempotency_miss")
    assert hits and any(getattr(e, "labels", {}).get("tool") == "write_count" for e in hits)
    assert misses and any(getattr(e, "labels", {}).get("tool") == "write_count" for e in misses)


@pytest.mark.asyncio
async def test_idempotency_key_reuse_with_different_arguments_rejected():
    registry = get_module_registry()
    await registry.register_module("counting_write_diff_args", _CountingWriteModule, ModuleConfig(name="counting_write_diff_args"))

    proto = MCPProtocol()
    proto.rbac_policy = AllowAllRBAC()

    ctx = RequestContext(request_id="id2", user_id="u1", client_id="c1")

    req1 = MCPRequest(method="tools/call", params={
        "name": "write_count",
        "arguments": {"x": "A"},
        "idempotencyKey": "k-diff-1",
    }, id="r1")
    resp1 = await proto.process_request(req1, ctx)
    assert resp1.error is None
    payload1 = resp1.result
    assert any(part.get("text", "").startswith("count:1:A") for part in payload1.get("content", []))

    # Reusing the same key with different args must fail explicitly.
    req2 = MCPRequest(method="tools/call", params={
        "name": "write_count",
        "arguments": {"x": "B"},
        "idempotencyKey": "k-diff-1",
    }, id="r2")
    resp2 = await proto.process_request(req2, ctx)
    assert resp2.error is not None
    assert resp2.error.code == -32602
    assert "idempotency key" in resp2.error.message.lower()


@pytest.mark.asyncio
async def test_idempotency_key_isolated_across_users():
    registry = get_module_registry()
    await registry.register_module("counting_write_user_isolation", _CountingWriteModule, ModuleConfig(name="counting_write_user_isolation"))

    proto = MCPProtocol()
    proto.rbac_policy = AllowAllRBAC()

    req = MCPRequest(method="tools/call", params={
        "name": "write_count",
        "arguments": {"x": "A"},
        "idempotencyKey": "k-shared",
    }, id="r1")

    resp_user_1 = await proto.process_request(req, RequestContext(request_id="u1", user_id="u1", client_id="c1"))
    assert resp_user_1.error is None
    payload_user_1 = resp_user_1.result
    assert any(part.get("text", "").startswith("count:1:A") for part in payload_user_1.get("content", []))

    resp_user_2 = await proto.process_request(
        MCPRequest(
            method="tools/call",
            params={"name": "write_count", "arguments": {"x": "A"}, "idempotencyKey": "k-shared"},
            id="r2",
        ),
        RequestContext(request_id="u2", user_id="u2", client_id="c1"),
    )
    assert resp_user_2.error is None
    payload_user_2 = resp_user_2.result
    assert any(part.get("text", "").startswith("count:2:A") for part in payload_user_2.get("content", []))


class _CategoryProbeLimiter:
    def __init__(self):
        self.last_category = None

    async def check_rate_limit(self, *args, **kwargs):
        self.last_category = kwargs.get("category")
        return True


class _CategoryModule(BaseModule):
    async def on_initialize(self) -> None:
        return None

    async def on_shutdown(self) -> None:
        return None

    async def check_health(self) -> Dict[str, bool]:
        return {"ok": True}

    async def get_tools(self) -> list[Dict[str, Any]]:
        # Explicit metadata category must be preferred by protocol
        return [create_tool_definition(
            name="echo_meta_ingestion",
            description="echo",
            parameters={"properties": {"m": {"type": "string"}}, "required": ["m"]},
            metadata={"category": "ingestion"},
        )]

    def validate_tool_arguments(self, tool_name: str, arguments: Dict[str, Any]):
        if "m" not in arguments:
            raise ValueError("m required")

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any], context=None):
        return arguments.get("m")


@pytest.mark.asyncio
async def test_category_prefers_metadata_over_config_mapping(monkeypatch):
    registry = get_module_registry()
    await registry.register_module("category_probe", _CategoryModule, ModuleConfig(name="category_probe"))

    proto = MCPProtocol()
    proto.rbac_policy = AllowAllRBAC()

    # Replace rate limiter with a probe
    probe = _CategoryProbeLimiter()
    proto.rate_limiter = probe

    ctx = RequestContext(request_id="cx1", user_id="u1", client_id="c1")
    req = MCPRequest(method="tools/call", params={"name": "echo_meta_ingestion", "arguments": {"m": "ok"}}, id="cx1")
    resp = await proto.process_request(req, ctx)
    assert resp.error is None
    # The category should be 'ingestion' from metadata
    assert probe.last_category == "ingestion"


@pytest.mark.asyncio
async def test_idempotency_local_lock_map_prunes_with_cache_bounds():
    manager = IdempotencyManager()

    async def _execute(value: str):
        return {"content": [{"type": "text", "text": value}]}

    for idx in range(10):
        key = f"k-{idx}"
        await manager.run(
            key,
            lambda i=idx: _execute(str(i)),
            ttl=1,
            max_size=3,
            lock_ttl=2,
        )

    # Local cache is size-bounded, and lock bookkeeping should track cache lifetime.
    assert len(manager._local_cache) <= 3
    assert len(manager._local_locks) <= 3
