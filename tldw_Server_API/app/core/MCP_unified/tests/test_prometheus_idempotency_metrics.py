import os
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.MCP_unified.modules.base import BaseModule, ModuleConfig, create_tool_definition
from tldw_Server_API.app.core.MCP_unified.modules.registry import get_module_registry
from tldw_Server_API.app.core.MCP_unified.auth.jwt_manager import get_jwt_manager


def _setup_env():
    os.environ["TEST_MODE"] = "true"
    os.environ["AUTH_MODE"] = "single_user"
    os.environ["SINGLE_USER_API_KEY"] = "test-api-key-1234567890"
    os.environ["SINGLE_USER_FIXED_ID"] = "1"
    os.environ["MCP_JWT_SECRET"] = "x" * 64
    os.environ["MCP_API_KEY_SALT"] = "s" * 64
    os.environ["MCP_PROMETHEUS_PUBLIC"] = "1"
    os.environ["MCP_TRUST_X_FORWARDED"] = "1"
    os.environ["MCP_ALLOWED_IPS"] = ""
    try:
        from tldw_Server_API.app.core.MCP_unified.config import get_config as _gc
        _gc.cache_clear()  # type: ignore[attr-defined]
    except Exception:
        pass
    try:
        from tldw_Server_API.app.core.MCP_unified.security.ip_filter import get_ip_access_controller as _gip
        _gip.cache_clear()  # type: ignore[attr-defined]
    except Exception:
        pass


class IdempWriteModule(BaseModule):
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
                name="idemp_write",
                description="Write with idempotency",
                parameters={
                    "properties": {"x": {"type": "string"}},
                    "required": ["x"],
                },
                metadata={"category": "ingestion"},
            )
        ]

    def validate_tool_arguments(self, tool_name: str, arguments: dict):
        if tool_name == "idemp_write":
            if not isinstance(arguments, dict) or "x" not in arguments:
                raise ValueError("'x' is required")

    async def execute_tool(self, tool_name: str, arguments: dict, context=None):
        return f"ok:{arguments.get('x')}"


@pytest.fixture(scope="module")
def client():
    _setup_env()
    from tldw_Server_API.app.api.v1.endpoints.mcp_unified_endpoint import router as mcp_router
    app = FastAPI()
    app.include_router(mcp_router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c


@pytest.mark.asyncio
async def test_prometheus_exports_idempotency_counters(client: TestClient):
    # Relax IP guard for tests
    from tldw_Server_API.app.core.MCP_unified.security.ip_filter import get_ip_access_controller
    ctrl = get_ip_access_controller()
    ctrl.trust_x_forwarded_for = True
    ctrl.allowed_networks = []
    ctrl.blocked_networks = []

    # Bypass RBAC in protocol
    from tldw_Server_API.app.core.MCP_unified import get_mcp_server
    class _AllowAll:
        async def check_permission(self, *args, **kwargs):
            return True
    get_mcp_server().protocol.rbac_policy = _AllowAll()

    # Register module
    reg = get_module_registry()
    await reg.register_module("idemp_mod", IdempWriteModule, ModuleConfig(name="idemp_mod"))

    token = get_jwt_manager().create_access_token(subject="1", roles=["admin"])  # auth for /request

    # First call (miss)
    req1 = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "idemp_write",
            "arguments": {"x": "A"},
            "idempotencyKey": "k-abc",
        },
        "id": "i1",
    }
    r1 = client.post(
        "/api/v1/mcp/request",
        json=req1,
        headers={"Authorization": f"Bearer {token}", "X-Forwarded-For": "127.0.0.1"},
    )
    assert r1.status_code == 200

    # Second call (hit)
    req2 = req1 | {"id": "i2"}
    r2 = client.post(
        "/api/v1/mcp/request",
        json=req2,
        headers={"Authorization": f"Bearer {token}", "X-Forwarded-For": "127.0.0.1"},
    )
    assert r2.status_code == 200

    # Scrape Prometheus metrics (public mode)
    r3 = client.get("/api/v1/mcp/metrics/prometheus", headers={"X-Forwarded-For": "127.0.0.1"})
    assert r3.status_code == 200
    text = r3.text
    # Expect idempotency miss + hit counters labeled for our tool
    assert "mcp_idempotency_misses_total" in text
    assert 'tool="idemp_write"' in text
    assert "mcp_idempotency_hits_total" in text
    assert 'tool="idemp_write"' in text
