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
    # Reset config/IP controller caches to pick up env
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


class StubWriteModule(BaseModule):
    async def on_initialize(self) -> None:
        return None

    async def on_shutdown(self) -> None:
        return None

    async def check_health(self) -> dict:
        return {"ready": True}

    async def get_tools(self) -> list[dict]:
        # A write-capable tool with required 'id' (schema) and custom validator
        return [
            create_tool_definition(
                name="delete_item",
                description="Delete an item",
                parameters={
                    "properties": {"id": {"type": "string"}},
                    "required": ["id"],
                },
                metadata={"category": "ingestion"},
            )
        ]

    def validate_tool_arguments(self, tool_name: str, arguments: dict):
        if tool_name == "delete_item":
            if not isinstance(arguments, dict) or not arguments.get("id"):
                raise ValueError("'id' is required")

    async def execute_tool(self, tool_name: str, arguments: dict, context=None):
        return "ok"


@pytest.fixture(scope="module")
def client():
    _setup_env()
    from tldw_Server_API.app.api.v1.endpoints.mcp_unified_endpoint import router as mcp_router
    app = FastAPI()
    app.include_router(mcp_router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c


@pytest.mark.asyncio
async def test_prometheus_exports_validation_counters(client: TestClient):
    # Relax IP guard dynamically for testclient
    from tldw_Server_API.app.core.MCP_unified.security.ip_filter import get_ip_access_controller
    try:
        ctrl = get_ip_access_controller()
        ctrl.trust_x_forwarded_for = True
        ctrl.allowed_networks = []
        ctrl.blocked_networks = []
    except Exception:
        pass
    # Bypass RBAC in protocol for this test
    from tldw_Server_API.app.core.MCP_unified import get_mcp_server
    class _AllowAll:
        async def check_permission(self, *args, **kwargs):
            return True
    get_mcp_server().protocol.rbac_policy = _AllowAll()

    # Register stub module
    reg = get_module_registry()
    await reg.register_module("stub_write", StubWriteModule, ModuleConfig(name="stub_write"))

    # Auth token
    token = get_jwt_manager().create_access_token(subject="1", roles=["admin"])  # ensure allowed

    # Trigger invalid params (missing id)
    bad = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {"name": "delete_item", "arguments": {}},
        "id": "m1",
    }
    r1 = client.post(
        "/api/v1/mcp/request",
        json=bad,
        headers={"Authorization": f"Bearer {token}", "X-Forwarded-For": "127.0.0.1"},
    )
    assert r1.status_code == 200
    body1 = r1.json()
    assert isinstance(body1, dict) and body1.get("error") is not None

    # Scrape Prometheus metrics (public mode)
    r2 = client.get("/api/v1/mcp/metrics/prometheus", headers={"X-Forwarded-For": "127.0.0.1"})
    assert r2.status_code == 200
    text = r2.text
    # Expect either schema or validator invalid counter present for our tool
    assert "mcp_tool_invalid_params_total" in text
    assert "tool=\"delete_item\"" in text


class StubWriteNoValidator(BaseModule):
    async def on_initialize(self) -> None:
        return None

    async def on_shutdown(self) -> None:
        return None

    async def check_health(self) -> dict:
        return {"ready": True}

    async def get_tools(self) -> list[dict]:
        # Marked as write-capable but without validate_tool_arguments override
        return [
            create_tool_definition(
                name="delete_item2",
                description="Delete an item (no validator)",
                parameters={
                    "properties": {"id": {"type": "string"}},
                    "required": ["id"],
                },
                metadata={"category": "ingestion"},
            )
        ]

    async def execute_tool(self, tool_name: str, arguments: dict, context=None):
        return "ok"


@pytest.mark.asyncio
async def test_prometheus_validator_missing_counter(client: TestClient):
    # Relax IP guard dynamically for testclient
    from tldw_Server_API.app.core.MCP_unified.security.ip_filter import get_ip_access_controller
    try:
        ctrl = get_ip_access_controller()
        ctrl.trust_x_forwarded_for = True
        ctrl.allowed_networks = []
        ctrl.blocked_networks = []
    except Exception:
        pass
    # Bypass RBAC in protocol for this test
    from tldw_Server_API.app.core.MCP_unified import get_mcp_server
    class _AllowAll:
        async def check_permission(self, *args, **kwargs):
            return True
    get_mcp_server().protocol.rbac_policy = _AllowAll()

    # Register module without validator override
    reg = get_module_registry()
    await reg.register_module("stub_write2", StubWriteNoValidator, ModuleConfig(name="stub_write2"))

    token = get_jwt_manager().create_access_token(subject="1", roles=["admin"])  # ensure allowed

    # Even with valid args, protocol should enforce validator presence and count it
    good = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {"name": "delete_item2", "arguments": {"id": "abc"}},
        "id": "m2",
    }
    r1 = client.post(
        "/api/v1/mcp/request",
        json=good,
        headers={"Authorization": f"Bearer {token}", "X-Forwarded-For": "127.0.0.1"},
    )
    assert r1.status_code == 200
    body1 = r1.json()
    assert isinstance(body1, dict) and body1.get("error") is not None

    # Scrape metrics and assert validator-missing counter appears
    r2 = client.get("/api/v1/mcp/metrics/prometheus", headers={"X-Forwarded-For": "127.0.0.1"})
    assert r2.status_code == 200
    text = r2.text
    assert "mcp_tool_validator_missing_total" in text
    assert "tool=\"delete_item2\"" in text
