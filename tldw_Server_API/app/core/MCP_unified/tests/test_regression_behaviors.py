import asyncio
from typing import Dict

import pytest
import pytest_asyncio

from tldw_Server_API.app.core.MCP_unified import get_mcp_server, reset_mcp_server
from tldw_Server_API.app.core.MCP_unified.modules.registry import ModuleRegistry
from tldw_Server_API.app.core.MCP_unified.protocol import (
    RequestContext,
    ErrorCode,
)
from tldw_Server_API.app.core.MCP_unified.config import get_config
from tldw_Server_API.app.core.MCP_unified.security.ip_filter import (
    get_ip_access_controller,
)
from tldw_Server_API.app.core.MCP_unified.auth import rate_limiter as rate_limiter_module
from tldw_Server_API.app.core.MCP_unified.auth.rate_limiter import RateLimiter


def _prepare_env(monkeypatch: pytest.MonkeyPatch, overrides: Dict[str, str]) -> None:
    defaults = {
        "TEST_MODE": "true",
        "AUTH_MODE": "single_user",
        "SINGLE_USER_API_KEY": "test-api-key-1234567890",
        "SINGLE_USER_FIXED_ID": "1",
        "MCP_JWT_SECRET": "x" * 64,
        "MCP_API_KEY_SALT": "s" * 64,
        "MCP_ALLOWED_IPS": "",
        "MCP_BLOCKED_IPS": "",
    }
    combined = {**defaults, **overrides}
    for key, value in combined.items():
        monkeypatch.setenv(key, value)

    try:
        get_config.cache_clear()  # type: ignore[attr-defined]
    except Exception:
        pass
    try:
        get_ip_access_controller.cache_clear()  # type: ignore[attr-defined]
    except Exception:
        pass


@pytest.mark.asyncio
async def test_module_registry_restarts_health_monitoring():
    registry = ModuleRegistry()
    await registry.start_health_monitoring()
    first_task = registry._health_check_task
    assert first_task is not None

    await registry.stop_health_monitoring()
    assert registry._health_check_task is None

    await registry.start_health_monitoring()
    second_task = registry._health_check_task
    assert second_task is not None
    assert second_task is not first_task

    await registry.stop_health_monitoring()


@pytest_asyncio.fixture
async def protocol(monkeypatch: pytest.MonkeyPatch):
    _prepare_env(monkeypatch, {"MCP_RATE_LIMIT_ENABLED": "false"})

    existing = getattr(rate_limiter_module, "_rate_limiter", None)
    if existing is not None:
        handle = getattr(existing, "_cleanup_task_handle", None)
        if handle:
            handle.cancel()
            try:
                await handle
            except asyncio.CancelledError:
                pass
    rate_limiter_module._rate_limiter = None  # type: ignore[attr-defined]

    await reset_mcp_server()
    server = get_mcp_server()

    class _AllowAll:
        async def check_permission(self, *args, **kwargs):
            return True

    server.protocol.rbac_policy = _AllowAll()
    try:
        yield server.protocol
    finally:
        await reset_mcp_server()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "request_payload,expected_message",
    [
        (
            {"jsonrpc": "2.0", "method": "tools/call", "params": {}, "id": "missing"},
            "Tool name is required",
        ),
        (
            {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": "does_not_exist", "arguments": {}},
                "id": "unknown",
            },
            "Tool not found: does_not_exist",
        ),
        (
            {"jsonrpc": "2.0", "method": "resources/read", "params": {}, "id": "res-missing"},
            "Resource URI is required",
        ),
        (
            {
                "jsonrpc": "2.0",
                "method": "prompts/get",
                "params": {},
                "id": "prompt-missing",
            },
            "Prompt name is required",
        ),
        (
            {
                "jsonrpc": "2.0",
                "method": "prompts/get",
                "params": {"name": "ghost"},
                "id": "prompt-unknown",
            },
            "Prompt not found: ghost",
        ),
    ],
)
async def test_protocol_maps_invalid_inputs(protocol, request_payload, expected_message):
    context = RequestContext(request_id=str(request_payload.get("id", "test")), user_id="1")
    response = await protocol.process_request(request_payload, context)
    assert response is not None
    assert response.error is not None
    assert response.error.code == ErrorCode.INVALID_PARAMS
    assert response.error.message == expected_message


@pytest.mark.asyncio
async def test_rate_limiter_schedules_cleanup_on_first_use(monkeypatch: pytest.MonkeyPatch):
    _prepare_env(
        monkeypatch,
        {
            "MCP_RATE_LIMIT_ENABLED": "true",
            "MCP_RATE_LIMIT_USE_REDIS": "false",
            "MCP_REDIS_URL": "",
        },
    )

    def _raise_no_loop():
        raise RuntimeError("no running loop")

    with monkeypatch.context() as m:
        m.setattr(asyncio, "get_running_loop", _raise_no_loop)
        limiter = RateLimiter()

    assert limiter._defer_cleanup is True
    assert limiter._cleanup_task_handle is None

    await limiter.check_rate_limit("user:test")
    assert limiter._cleanup_task_handle is not None
    assert not limiter._cleanup_task_handle.done()

    limiter._cleanup_task_handle.cancel()
    try:
        await limiter._cleanup_task_handle
    except asyncio.CancelledError:
        pass
