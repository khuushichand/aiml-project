"""Category-specific rate limit tests for MCP Unified."""

import pytest
from typing import Dict, Any, List

from tldw_Server_API.app.core.MCP_unified.modules.base import BaseModule, ModuleConfig
from tldw_Server_API.app.core.MCP_unified.modules.registry import get_module_registry
from tldw_Server_API.app.core.MCP_unified.server import MCPServer
from tldw_Server_API.app.core.MCP_unified.protocol import MCPRequest
from tldw_Server_API.app.core.MCP_unified.config import get_config
from fastapi import HTTPException



class StubCategoryModule(BaseModule):
    async def on_initialize(self) -> None: ...
    async def on_shutdown(self) -> None: ...
    async def check_health(self) -> Dict[str, bool]:
        return {"ok": True}
    async def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "mock_ingest",
                "description": "",
                "inputSchema": {"type": "object"},
                "metadata": {"category": "ingestion"},
            },
            {
                "name": "mock_read",
                "description": "",
                "inputSchema": {"type": "object"},
                "metadata": {"category": "read"},
            },
        ]
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any], context: Any | None = None) -> Any:
        return f"ok:{tool_name}"
    def validate_tool_arguments(self, tool_name: str, arguments: Dict[str, Any]) -> None:
        # Tests only need the validator hook to exist; no real validation required.
        return None


@pytest.mark.asyncio
async def test_category_limits_ingestion_vs_read(monkeypatch):
    # Configure mapping and strict ingestion RPM
    monkeypatch.setenv("MCP_TOOL_CATEGORY_MAP", '{"mock_ingest":"ingestion","mock_read":"read"}')
    monkeypatch.setenv("MCP_RATE_LIMIT_RPM_INGESTION", "1")
    monkeypatch.setenv("MCP_RATE_LIMIT_RPM_READ", "999")
    monkeypatch.setenv("MCP_RATE_LIMIT_BURST_INGESTION", "1")
    # Reset config cache to pick up env
    try:
        get_config.cache_clear()  # type: ignore[attr-defined]
    except Exception:
        pass

    server = MCPServer()
    await server.initialize()
    # Disable RBAC by allowing all for test
    class _AllowAll:
        async def check_permission(self, *args, **kwargs):
            return True
    server.protocol.rbac_policy = _AllowAll()

    # Register stub module
    reg = server.module_registry
    await reg.register_module("stub", StubCategoryModule, ModuleConfig(name="stub"))

    # Helper to call tools via HTTP path (returns MCPResponse or raises HTTPException)
    async def call_tool(name: str):
        req = MCPRequest(method="tools/call", params={"name": name, "arguments": {"x": 1}}, id="t1")
        return await server.handle_http_request(req, user_id="u1")

    # First ingest call should pass
    r1 = await call_tool("mock_ingest")
    assert r1.error is None
    # Token-bucket priming allows one additional burst request; third should rate limit
    r2 = await call_tool("mock_ingest")
    assert r2.error is None
    with pytest.raises(HTTPException) as ei:
        await call_tool("mock_ingest")
    assert ei.value.status_code == 429

    # Read calls should be allowed liberally
    r2 = await call_tool("mock_read")
    assert r2.error is None
    r3 = await call_tool("mock_read")
    assert r3.error is None

    await server.shutdown()
